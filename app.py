import os
import json
import base64
import difflib
import requests
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
FDA_API_KEY = os.environ.get("FDA_API_KEY", "")
GEMINI_MODEL = "gemini-flash-latest"

with open(os.path.join(os.path.dirname(__file__), "drug_data.json")) as f:
    DRUG_DB = json.load(f)

EXTRACTION_PROMPT = """You are reading a medical prescription image, which may be handwritten or printed.
Extract every medication mentioned. Also find the bounding box for each medication in the image.
Respond ONLY with valid JSON — no markdown, no commentary — in this exact shape:

{
  "medications": [
    {
      "raw_text": "the text as best you can read it",
      "drug_name": "your best reading of the drug name, lowercase",
      "dosage_amount": <number or null>,
      "dosage_unit": "mg" | "ml" | "unknown",
      "frequency_per_day": <integer or null>,
      "duration_days": <integer or null>,
      "confidence": <0-100 integer, your confidence in this extraction>,
      "box_2d": [ymin, xmin, ymax, xmax]  // Normalized coordinates on 0-1000 scale (integers)
    }
  ],
  "patient_name": "string or null",
  "doctor_name": "string or null",
  "date": "string or null"
}

If handwriting is ambiguous, make your best clinical guess and lower the confidence score accordingly.
If you cannot read a field, set it to null rather than guessing wildly.

IMPORTANT: Inside string fields (like raw_text, drug_name, patient_name, doctor_name), replace any double-quotes with single-quotes or ensure they are properly escaped as \\" to prevent JSON parse errors.
"""


# ---------------------------------------------------------------------------
# Gemini extraction
# ---------------------------------------------------------------------------
def clean_and_parse_json(text: str) -> dict:
    """Cleans and robustly parses JSON, repairing common issues like unescaped internal double-quotes and missing commas."""
    text = text.strip()
    
    # Strip any extra text/markdown outside of the root JSON object
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx:end_idx + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        import re
        
        # Split into lines to inspect and repair syntax
        lines = text.splitlines()
        repaired_lines = []
        
        for idx in range(len(lines)):
            line = lines[idx].rstrip()
            if not line:
                repaired_lines.append(line)
                continue
                
            # 1. Escape unescaped double quotes inside value strings
            match = re.match(r'^(\s*"[^"]+"\s*:\s*")(.*)("\s*,?\s*)$', line)
            if match:
                key_part, val_part, end_part = match.groups()
                # Escape any unescaped double quotes inside value part
                escaped_val = re.sub(r'(?<!\\)"', r'\"', val_part)
                line = f"{key_part}{escaped_val}{end_part}"
            
            repaired_lines.append(line)
            
        # 2. Add missing commas between key-value pairs
        final_lines = []
        for idx in range(len(repaired_lines)):
            line = repaired_lines[idx].rstrip()
            if not line:
                final_lines.append(line)
                continue
                
            # If this is not the last line, check if the next non-empty line starts with a key
            if idx < len(repaired_lines) - 1:
                next_non_empty = ""
                for j in range(idx + 1, len(repaired_lines)):
                    if repaired_lines[j].strip():
                        next_non_empty = repaired_lines[j].strip()
                        break
                
                if next_non_empty and re.match(r'^"[^"]+"\s*:', next_non_empty):
                    last_char = line[-1]
                    if last_char not in (',', '{', '[') and not line.strip().endswith('}'):
                        line = line + ','
            
            final_lines.append(line)
            
        reconstructed = "\n".join(final_lines)
        try:
            return json.loads(reconstructed)
        except Exception:
            # If secondary repair parse fails, raise the original JSONDecodeError
            raise e


def extract_with_gemini(image_bytes: bytes, mime_type: str) -> dict:
    """Calls Gemini's vision API to extract structured prescription data."""
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    image_part = {"mime_type": mime_type, "data": image_bytes}
    response = model.generate_content(
        [EXTRACTION_PROMPT, image_part],
        generation_config={"response_mime_type": "application/json"},
    )
    return clean_and_parse_json(response.text)


def mock_extraction() -> dict:
    """Fallback so the app is demoable even without an API key set."""
    return {
        "patient_name": "Demo Patient",
        "doctor_name": "Dr. Suresh",
        "date": "2026-07-17",
        "medications": [
            {"raw_text": "Tab. Paracetamol 650mg TDS x5d", "drug_name": "paracetamol",
             "dosage_amount": 650, "dosage_unit": "mg", "frequency_per_day": 3,
             "duration_days": 5, "confidence": 88, "box_2d": [300, 200, 360, 800]},
            {"raw_text": "Tab. Warfarin 5mg OD", "drug_name": "warfarin",
             "dosage_amount": 5, "dosage_unit": "mg", "frequency_per_day": 1,
             "duration_days": 30, "confidence": 76, "box_2d": [450, 200, 510, 800]},
            {"raw_text": "Tab. Aspirin 75mg OD", "drug_name": "aspirin",
             "dosage_amount": 75, "dosage_unit": "mg", "frequency_per_day": 1,
             "duration_days": 30, "confidence": 91, "box_2d": [600, 200, 660, 800]},
            {"raw_text": "Tab. Xyzmol (illegible)", "drug_name": "xyzmol",
             "dosage_amount": None, "dosage_unit": "unknown", "frequency_per_day": None,
             "duration_days": None, "confidence": 22, "box_2d": [750, 200, 810, 800]},
        ],
    }


# ---------------------------------------------------------------------------
# openFDA Helpers
# ---------------------------------------------------------------------------
FDA_GENERIC_NAMES = {
    "paracetamol": "acetaminophen",
    "acetaminophen": "acetaminophen",
    "ibuprofen": "ibuprofen",
    "amoxicillin": "amoxicillin",
    "metformin": "metformin",
    "amlodipine": "amlodipine",
    "azithromycin": "azithromycin",
    "warfarin": "warfarin",
    "aspirin": "aspirin",
    "omeprazole": "omeprazole",
    "cetirizine": "cetirizine",
    "atorvastatin": "atorvastatin",
    "losartan": "losartan",
    "insulin": "insulin"
}


def query_openfda_label(drug_name: str) -> dict:
    """Queries openFDA API for a drug's label information (boxed warning, interactions, warnings)."""
    if not drug_name:
        return None

    # Map to standard FDA generic name if recognized locally
    search_term = FDA_GENERIC_NAMES.get(drug_name.lower(), drug_name.lower())
    
    # Base URL
    url = f'https://api.fda.gov/drug/label.json?search=openfda.generic_name:"{search_term}"+openfda.brand_name:"{search_term}"&limit=1'
    if FDA_API_KEY:
        url += f"&api_key={FDA_API_KEY}"
        
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]
        
        # Fallback to keyless/quoteless search
        url_fallback = f'https://api.fda.gov/drug/label.json?search=openfda.generic_name:{search_term}&limit=1'
        if FDA_API_KEY:
            url_fallback += f"&api_key={FDA_API_KEY}"
            
        r = requests.get(url_fallback, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]
    except Exception:
        pass
    return None


def check_dynamic_interactions(medications_data: list) -> list:
    """Detects interactions dynamically by searching other drug names in each drug's FDA label warnings."""
    dynamic_flags = [[] for _ in range(len(medications_data))]
    
    for i in range(len(medications_data)):
        for j in range(len(medications_data)):
            if i == j:
                continue
            
            med_a = medications_data[i]
            med_b = medications_data[j]
            
            # Identify name variants for B to search in A's warnings
            names_to_search = set()
            for key in ["drug_name", "canonical_name", "fda_generic_name"]:
                val = med_b.get(key)
                if val:
                    names_to_search.add(val.lower())
                    # Also map paracetamol/acetaminophen synonyms
                    if val.lower() == "paracetamol":
                        names_to_search.add("acetaminophen")
                    elif val.lower() == "acetaminophen":
                        names_to_search.add("paracetamol")
            
            # Retrieve A's label texts
            label = med_a.get("fda_label")
            if not label:
                continue
                
            warnings_text = ""
            for field in ["drug_interactions", "warnings_and_precautions", "warnings", "boxed_warning", "contraindications"]:
                if field in label:
                    val = label[field]
                    if isinstance(val, list):
                        warnings_text += " ".join(val).lower()
                    elif isinstance(val, str):
                        warnings_text += val.lower()
            
            # Check if any of B's names are mentioned in A's warnings text
            for name in names_to_search:
                if len(name) > 3 and name in warnings_text:
                    dynamic_flags[i].append({
                        "level": "red" if "boxed_warning" in label else "yellow",
                        "message": f"FDA Warning: Potential interaction with '{med_b.get('canonical_name') or med_b.get('drug_name')}' found in FDA label."
                    })
                    break
                    
    return dynamic_flags


def verify_fda_match(search_term: str, fda_label: dict) -> bool:
    """Verifies that the retrieved openFDA label is a true match for the search term."""
    if not fda_label or not search_term:
        return False
        
    search_term = search_term.lower().strip()
    openfda = fda_label.get("openfda", {})
    
    brand_names = [b.lower() for b in openfda.get("brand_name", [])]
    generic_names = [g.lower() for g in openfda.get("generic_name", [])]
    substance_names = [s.lower() for s in openfda.get("substance_name", [])]
    
    # 1. Exact match on any of the lists
    if search_term in brand_names or search_term in generic_names or search_term in substance_names:
        return True
        
    # 2. Check if the search term is the FIRST word of any generic, brand or substance name
    # (e.g. "dextrose" matches "dextrose monohydrate...")
    for name in generic_names + brand_names + substance_names:
        words = name.replace(",", " ").replace("(", " ").replace(")", " ").split()
        if words and words[0] == search_term:
            return True
            
    # 3. For multi-word search terms, check if all words are present
    search_words = search_term.split()
    if len(search_words) > 1:
        for name in generic_names + brand_names + substance_names:
            if all(w in name for w in search_words):
                return True
                
    return False


# ---------------------------------------------------------------------------
# Normalization + validation
# ---------------------------------------------------------------------------
def resolve_rxnorm(drug_name: str) -> dict:
    """Queries NLM RxNorm REST API to find the CUI and standardized name for a drug."""
    if not drug_name:
        return None
        
    import urllib.parse
    encoded_name = urllib.parse.quote_plus(drug_name.strip())
    
    # 1. Try exact/normalized match
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={encoded_name}"
    try:
        r = requests.get(url, timeout=2)
        if r.status_code == 200:
            data = r.json()
            id_group = data.get("idGroup", {})
            rxcui = id_group.get("rxnormId")
            if rxcui:
                # Retrieve properties to fetch official name
                prop_url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}.json"
                prop_r = requests.get(prop_url, timeout=2)
                if prop_r.status_code == 200:
                    prop_data = prop_r.json()
                    name = prop_data.get("rxnormdata", {}).get("idGroup", {}).get("name")
                    return {"rxcui": rxcui, "name": name or drug_name}
    except Exception:
        pass
        
    # 2. Try approximate match fallback (for OCR spelling correction)
    url_approx = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={encoded_name}&maxEntries=1"
    try:
        r = requests.get(url_approx, timeout=2)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("approximateGroup", {}).get("candidate", [])
            if candidates:
                rxcui = candidates[0].get("rxcui")
                if rxcui:
                    prop_url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}.json"
                    prop_r = requests.get(prop_url, timeout=2)
                    if prop_r.status_code == 200:
                        prop_data = prop_r.json()
                        name = prop_data.get("rxnormdata", {}).get("idGroup", {}).get("name")
                        return {"rxcui": rxcui, "name": name or drug_name}
    except Exception:
        pass
        
    return None


def normalize_drug_name(raw_name: str):
    if not raw_name:
        return None, 0
    raw_name = raw_name.strip().lower()
    if raw_name in DRUG_DB["aliases"]:
        return DRUG_DB["aliases"][raw_name], 100

    matches = difflib.get_close_matches(raw_name, DRUG_DB["aliases"].keys(), n=1, cutoff=0.72)
    if matches:
        return DRUG_DB["aliases"][matches[0]], 70
    return None, 0


def validate_medications(medications: list, patient_profile: dict = None) -> list:
    # 1. Resolve names via RxNorm (in parallel) and prepare FDA search terms
    rxnorm_results = []
    query_names = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        rx_futures = [executor.submit(resolve_rxnorm, med.get("drug_name", "")) for med in medications]
        for f in rx_futures:
            try:
                rxnorm_results.append(f.result())
            except Exception:
                rxnorm_results.append(None)

    for idx, med in enumerate(medications):
        rx_info = rxnorm_results[idx]
        std_name = rx_info["name"] if rx_info else med.get("drug_name", "")
        
        canonical, _ = normalize_drug_name(std_name)
        query_names.append(canonical or std_name)

    # 2. Parallel fetch FDA label data for all medications
    with ThreadPoolExecutor(max_workers=5) as executor:
        fda_labels = list(executor.map(query_openfda_label, query_names))

    results = []
    normalized_names = []

    for idx, med in enumerate(medications):
        flags = []
        rx_info = rxnorm_results[idx]
        rxcui = rx_info["rxcui"] if rx_info else None
        std_name = rx_info["name"] if rx_info else med.get("drug_name", "")
        
        raw_name = med.get("drug_name", "")
        canonical, match_confidence = normalize_drug_name(std_name)
        if not canonical:
            canonical, match_confidence = normalize_drug_name(raw_name)
            
        normalized_names.append(canonical)

        # FDA metadata population
        fda_label = fda_labels[idx]
        fda_status = "not_found"
        fda_generic_name = None
        fda_boxed_warning = None
        
        # Verify FDA match using our verification function (check standard_name and raw_name)
        if fda_label and not (verify_fda_match(query_names[idx], fda_label) or verify_fda_match(raw_name, fda_label)):
            fda_label = None  # Discard mismatching label
            
        if fda_label:
            fda_status = "found"
            openfda_meta = fda_label.get("openfda", {})
            if "generic_name" in openfda_meta and len(openfda_meta["generic_name"]) > 0:
                fda_generic_name = openfda_meta["generic_name"][0]
            elif "brand_name" in openfda_meta and len(openfda_meta["brand_name"]) > 0:
                fda_generic_name = openfda_meta["brand_name"][0]
            
            # Extract boxed warning
            if "boxed_warning" in fda_label and len(fda_label["boxed_warning"]) > 0:
                fda_boxed_warning = fda_label["boxed_warning"][0]
                warning_desc = fda_boxed_warning
                if len(warning_desc) > 150:
                    warning_desc = warning_desc[:147] + "..."
                flags.append({"level": "red", "message": f"FDA Boxed Warning: {warning_desc}"})

        # Standard check
        if canonical is None and fda_status == "not_found":
            flags.append({"level": "red", "message": "Drug name not recognized — verify manually with pharmacist."})
        elif raw_name.lower().strip() != std_name.lower().strip() and rxcui:
            flags.append({"level": "yellow", "message": f"Resolved via RxNorm spelling correction to '{std_name}' (RxCUI: {rxcui})."})
        elif match_confidence < 100 and canonical is not None:
            flags.append({"level": "yellow", "message": f"Name auto-corrected to '{canonical}' — please confirm."})

        if med.get("confidence", 0) < 50:
            flags.append({"level": "yellow", "message": "Low OCR confidence — handwriting was hard to read."})

        if not med.get("frequency_per_day"):
            flags.append({"level": "yellow", "message": "Frequency not specified."})
        if not med.get("duration_days"):
            flags.append({"level": "yellow", "message": "Duration not specified."})

        # Dosage check
        if canonical and canonical in DRUG_DB["dosage_limits"] and med.get("dosage_amount"):
            limits = DRUG_DB["dosage_limits"][canonical]
            single = med["dosage_amount"]
            daily = single * (med.get("frequency_per_day") or 1)
            if single > limits["max_single_mg"]:
                flags.append({"level": "red", "message": f"Single dose ({single}mg) exceeds typical max ({limits['max_single_mg']}mg)."})
            if daily > limits["max_daily_mg"]:
                flags.append({"level": "red", "message": f"Daily dose ({daily}mg) exceeds typical max ({limits['max_daily_mg']}mg)."})

        # Contraindications check
        if patient_profile:
            conditions = patient_profile.get("conditions", [])
            is_pregnant = patient_profile.get("pregnancy") == "yes"
            
            for rule in DRUG_DB.get("contraindications", []):
                rule_drug = rule["drug"].lower()
                matches_drug = (
                    (canonical and canonical == rule_drug) or
                    (fda_generic_name and rule_drug in fda_generic_name.lower())
                )
                if matches_drug:
                    rule_cond = rule["condition"]
                    is_match = False
                    if rule_cond == "pregnancy" and is_pregnant:
                        is_match = True
                    elif rule_cond in conditions:
                        is_match = True
                        
                    if is_match:
                        flags.append({
                            "level": rule["severity"],
                            "message": f"Contraindication ({rule_cond.replace('_', ' ').capitalize()}): {rule['note']}"
                        })

        # Default green if no warnings are added yet
        if not flags:
            flags.append({"level": "green", "message": "Looks consistent with standard dosing."})

        results.append({
            **med,
            "canonical_name": canonical,
            "rxcui": rxcui,
            "flags": flags,
            "fda_status": fda_status,
            "fda_generic_name": fda_generic_name,
            "fda_boxed_warning": fda_boxed_warning,
            "fda_label": fda_label  # Keep temporary for dynamic interaction checks
        })

    # 2. Local Database Cross-drug interaction check
    for interaction in DRUG_DB["interactions"]:
        a, b = interaction["pair"]
        if a in normalized_names and b in normalized_names:
            for med in results:
                if med["canonical_name"] in (a, b):
                    med["flags"].append({
                        "level": "red" if interaction["severity"] == "high" else "yellow",
                        "message": f"Interaction with {b if med['canonical_name'] == a else a}: {interaction['note']}",
                    })

    # 3. Dynamic openFDA Interaction check
    dynamic_flags = check_dynamic_interactions(results)
    for idx, med in enumerate(results):
        med["flags"].extend(dynamic_flags[idx])

    # 4. Clean up temporary fields and adjust green flags
    for med in results:
        med.pop("fda_label", None)
        has_warning = any(f["level"] in ("red", "yellow") for f in med["flags"])
        if has_warning:
            med["flags"] = [f for f in med["flags"] if f["level"] != "green"]

    return results


def overall_severity(results: list) -> str:
    levels = [f["level"] for med in results for f in med["flags"]]
    if "red" in levels:
        return "red"
    if "yellow" in levels:
        return "yellow"
    return "green"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    image_bytes = file.read()
    mime_type = file.mimetype or "image/jpeg"

    try:
        if GEMINI_API_KEY:
            extraction = extract_with_gemini(image_bytes, mime_type)
        else:
            extraction = mock_extraction()
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500

    validated = validate_medications(extraction.get("medications", []))

    return jsonify({
        "patient_name": extraction.get("patient_name"),
        "doctor_name": extraction.get("doctor_name"),
        "date": extraction.get("date"),
        "medications": validated,
        "overall_severity": overall_severity(validated),
        "using_mock_data": not bool(GEMINI_API_KEY),
    })


@app.route("/api/validate", methods=["POST"])
def validate():
    data = request.json or {}
    medications = data.get("medications", [])
    patient_profile = data.get("patient_profile", {})
    
    validated = validate_medications(medications, patient_profile)
    
    return jsonify({
        "medications": validated,
        "overall_severity": overall_severity(validated)
    })


@app.route("/api/share", methods=["POST"])
def share():
    data = request.json or {}
    phone = data.get("phone", "")
    patient_name = data.get("patient_name", "Patient")
    medications = data.get("medications", [])
    overall = data.get("overall_severity", "green")
    
    severity_label = {
        "red": "CRITICAL WARNINGS — Review immediately",
        "yellow": "MINOR FLAGS — Proceed with caution",
        "green": "Looks safe to proceed"
    }.get(overall, "Verified")
    
    sms_lines = [
        f"PrescriptoSafe Report for {patient_name}",
        f"Safety Summary: {severity_label}",
        "Medications Checked:"
    ]
    
    for med in medications:
        name = med.get("canonical_name") or med.get("drug_name") or "Unknown"
        dose = med.get("dosage_amount", "")
        unit = med.get("dosage_unit", "")
        freq = med.get("frequency_per_day", "")
        duration = med.get("duration_days", "")
        
        dosage_str = f"{dose}{unit}" if dose else "unspecified"
        schedule_str = f"{freq}x/day" if freq else ""
        dur_str = f"{duration}d" if duration else ""
        
        details = " · ".join(filter(None, [dosage_str, schedule_str, dur_str]))
        
        warnings = [f["message"] for f in med.get("flags", []) if f["level"] in ("red", "yellow")]
        warn_str = f" ({len(warnings)} flag(s))" if warnings else " (Safe)"
        
        sms_lines.append(f"- {name.capitalize()} [{details}]{warn_str}")
        
    sms_text = "\n".join(sms_lines)
    
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_from = os.environ.get("TWILIO_FROM_NUMBER")
    
    sent_real = False
    error_msg = None
    
    if twilio_sid and twilio_token and twilio_from and phone:
        try:
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            if twilio_from.startswith("MG"):
                client.messages.create(
                    body=sms_text,
                    messaging_service_sid=twilio_from,
                    to=phone
                )
            else:
                client.messages.create(
                    body=sms_text,
                    from_=twilio_from,
                    to=phone
                )
            sent_real = True
        except Exception as e:
            error_msg = str(e)
            
    return jsonify({
        "status": "success",
        "sent_real": sent_real,
        "message": sms_text,
        "error": error_msg
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
