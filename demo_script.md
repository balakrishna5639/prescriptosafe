# PrescriptoSafe Video Demo Script

This is a customized demo script for the video recording based on the prescription scan from **The White Tusk** for **Mr. Sachin Sansare**.

---

## 🎙️ Video Script (2-3 Minutes)

### 1. The Hook (15 seconds)
> *"Every year, millions of medication errors occur worldwide due to illegible handwritten prescriptions. Today, we are verifying a dental prescription from 'The White Tusk' dental clinic for a patient named Mr. Sachin Sansare."*

### 2. The Upload & PACS Scanner (20 seconds)
> *"We drag and drop the prescription photo into PrescriptoSafe. Immediately, the PACS-style clinical monitor opens and a vertical neon-green laser line sweeps down the scan, digitizing the handwriting and querying NLM RxNorm and openFDA databases in parallel."*

### 3. Bounding Boxes & Bidirectional Hover (30 seconds)
> *"Once processed, the split-screen dashboard appears. Notice the neon-blue highlight boxes mapped precisely around the handwritten medication text. Hovering over a box on the scan immediately scrolls to and highlights the corresponding editable card on the right, keeping raw handwriting connected to clean digital entries."*

### 4. Terminology Standardisation (30 seconds)
> *"The system automatically resolves 'Augmentin 625mg' and 'Pan-D' using NLM RxNorm API, attaching official clinical standard RxCUI codes (like RxCUI: 1009187) and verifying them against openFDA labels in real-time."*

### 5. Real-time Patient Profile Simulation (45 seconds)
> *"Our patient, Sachin, is a 28-year-old male. Let's simulate a clinical condition. 'Enzoflam' is a combination tablet containing Diclofenac (an NSAID). If we check the **Kidney Disease** box in the Patient Profile form, the safety validation engine instantly recalculates: the Enzoflam card flashes red, flagging a high-severity contraindication warning because NSAIDs are contraindicated in renal impairment.*
> 
> *If we check **Asthma**, it flags a warning about NSAID-induced bronchospasms. The overall safety badge automatically switches from green to red in real-time."*

### 6. SMS Sharing & Closing (20 seconds)
> *"We click 'Share Report via SMS', type in the patient's number, and a formatted safety report is delivered to their mobile device via Twilio. PrescriptoSafe acts as an instant, zero-setup clinical shield working from any phone camera."*
