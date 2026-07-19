# PrescriptoSafe

AI-powered prescription digitization & advanced clinical safety verification suite — built for the NxtWave Online Hackathon (Theme 3: Crisis Management, HealthTech & Emergency Response).

PrescriptoSafe is a high-fidelity clinical decision support tool designed to serve as a digital safety net. By combining **Multimodal Gemini AI**, NLM's **RxNorm terminology services**, the official **openFDA database**, and a **Twilio SMS communication layer**, PrescriptoSafe turns messy prescription scans into a clean, interactive, and clinically verified safety report.

---

## 🌟 Advanced Features Built

1. **OCR Scanning & Bounding Boxes Overlay**:
   - Extracts structured prescription data from handwritten or printed photos.
   - Plots responsive, neon-blue coordinate bounding boxes over the scanned image.
   - Bidirectional hover selection: Hovering a coordinate highlight highlights the medication card, and vice versa.

2. **PACS-Style Medical Scanner Interface**:
   - Modern PACS dark-obsidian scan frame.
   - Features a vertical **neon-green laser sweep animation** while the AI extracts details, showing active digitization.

3. **NLM RxNorm Integration**:
   - Resolves OCR spellings and typos (e.g. `combigen` -> `Combigan`, `azopt sticy` -> `Azopt`) by querying NLM RxNorm APIs.
   - Attaches official indigo-colored **RxCUI Code Badges** (RxNorm Concept Unique Identifiers) to medications.
   - Alerts the clinician about auto-corrected spelling mappings.

4. **openFDA Dynamic Verification**:
   - Queries the openFDA label database in parallel.
   - Populates official generic names and pulls **FDA Boxed Warnings** (shown as clinical red alert cards).
   - Runs cross-drug interaction checks dynamically by searching other prescription items inside each drug's labeling warnings.

5. **Patient Profile & Clinical Contraindications**:
   - A dedicated patient metadata form (Age, Pregnancy status, and checkboxes for Kidney Disease, Asthma, Hypertension, Heart Failure).
   - Cross-checks inputs against clinical contraindication rules (e.g., NSAIDs like Ibuprofen/Aspirin in pregnancy, Metformin in kidney disease, Amlodipine in heart failure).

6. **Interactive Side-by-Side Editor (Real-time Recalculations)**:
   - Split layout: Image pane on the left, editable profile and dosage form cards on the right.
   - Auto-saves inputs and triggers debounced validation requests, updating alerts and overall severity badges in real-time.
   - Displays a pulsing **"Validating safety..."** loader animation next to the header during live compilation so clinicians have instant progress feedback.

7. **Twilio SMS Sharing (Sandbox & Live)**:
   - Share a copy of the clinical safety report directly to the patient's phone.
   - Automatically detects missing credentials in `.env` and defaults to a simulated sandbox dialog box, ensuring demo safety.

8. **Session Caching**:
   - Stores the Base64 image, parsed medications, and patient profile details in `localStorage`.
   - Stays fully persistent across accidental page reloads, and clears cleanly when checking another prescription.

---

## 🛠 Run locally

```bash
# Clone or navigate to repository folder
# Activate virtual environment
venv\Scripts\activate      # Linux/macOS: source venv/bin/activate

# Install dependencies (updated with twilio & requests)
pip install -r requirements.txt

# Start local server
python app.py
```

Visit `http://localhost:5000` in your web browser.

---

## ⚙️ Environment Configuration (`.env`)
Create a `.env` file in the root folder with the following variables:
```env
GEMINI_API_KEY=your_gemini_api_key_here
PORT=5000
FDA_API_KEY=your_open_fda_api_key_here

# Twilio SMS Config (Optional, falls back to simulation mode if empty)
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+16055256022
```

---

## 📂 Project Structure
```
prescriptosafe/
├── app.py                 # Flask server, regex JSON repairer, openFDA & RxNorm fetchers
├── drug_data.json         # Local database (aliases, contraindications, dosage limits)
├── requirements.txt       # Dependencies
├── .env                   # Local variables (gitignored)
├── templates/
│   └── index.html         # Split-screen responsive layout & sharing modals
└── static/
    ├── css/style.css      # Clinical Slate styles, laser scanning & pulse animations
    └── js/app.js          # SVG icons, bounding box plotting, localStorage cache, API connections
```

---

## 🚀 Hackathon Demo Script (2-3 Minutes)
1. **The Hook (15s)**: "Every year, millions of medication errors occur due to illegible handwritten prescriptions. Today, we are verifying a dental prescription from *The White Tusk* clinic for patient *Mr. Sachin Sansare*."
2. **The Upload & PACS Scanner (20s)**: "We drop the photo into PrescriptoSafe. The PACS-style clinical monitor opens and a vertical laser line sweeps down the scan, digitizing the handwriting and querying NLM RxNorm and openFDA databases in parallel."
3. **Interactive Grid & Coordinate Overlays (30s)**: "Once processed, the split-screen dashboard appears. Bounding boxes highlight the exact position of the text on the scan. Hovering over a bounding box immediately highlights the corresponding editable medication card on the right, keeping raw handwriting connected to clean digital entries."
4. **Clinical Standardisation (30s)**: "Notice how the system standardizes `Augmentin` and `Pan-D`, pulling their official NLM **RxCUI codes** and **FDA labels** in real-time, validating dosages against the clinical knowledge base."
5. **Real-time Patient Profile Simulation (45s)**: 
   - "Our patient, Sachin, is a 28-year-old male. Let's see what happens if we simulate a comorbidity. *Enzoflam* contains Diclofenac (an NSAID). If we check the **Kidney Disease** box in the Patient Profile form, the validation engine instantly recalculates: the Enzoflam card flashes red, flagging a high-severity warning because NSAIDs are contraindicated in renal impairment."
   - "Check **Asthma** -> Enzoflam triggers a warning about NSAID-induced bronchospasms in aspirin-sensitive patients. The overall safety badge changes from green to red in real-time."
6. **SMS Report Sharing & Closing (20s)**: "Click **Share Report via SMS** and enter the patient's number. A formatted safety report detailing the check is sent directly to their phone via Twilio. PrescriptoSafe acts as an instant, zero-setup clinical shield."
