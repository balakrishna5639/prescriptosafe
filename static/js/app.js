const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const previewImg = document.getElementById('previewImg');
const dropzoneContent = document.getElementById('dropzoneContent');
const analyzeBtn = document.getElementById('analyzeBtn');

const uploadSection = document.getElementById('upload-section');
const loadingSection = document.getElementById('loading-section');
const resultsSection = document.getElementById('results-section');
const mockNotice = document.getElementById('mockNotice');

const resultsPreviewImg = document.getElementById('resultsPreviewImg');
const canvasOverlay = document.getElementById('canvasOverlay');
const loadingPreviewImg = document.getElementById('loadingPreviewImg');

// Profile Elements
const patientNameInput = document.getElementById('patientNameInput');
const patientAgeInput = document.getElementById('patientAgeInput');
const patientPregnancyInput = document.getElementById('patientPregnancyInput');
const medsFormList = document.getElementById('medsFormList');
const validationLoader = document.getElementById('validationLoader');

// Sharing Elements
const shareBtn = document.getElementById('shareBtn');
const shareModal = document.getElementById('shareModal');
const closeModal = document.querySelector('.close-modal');
const sharePhoneInput = document.getElementById('sharePhoneInput');
const sendShareBtn = document.getElementById('sendShareBtn');
const shareStatus = document.getElementById('shareStatus');

const resetBtn = document.getElementById('resetBtn');

let selectedFile = null;
let currentData = null; // Stores currently loaded analysis data

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length) handleFile(e.target.files[0]);
});

function handleFile(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target.result;
    previewImg.src = base64;
    previewImg.hidden = false;
    dropzoneContent.hidden = true;
    analyzeBtn.disabled = false;
    
    // Load into the results preview and loading preview images
    resultsPreviewImg.src = base64;
    loadingPreviewImg.src = base64;
    
    // Save image to localStorage
    try {
      localStorage.setItem('prescriptosafe_image', base64);
    } catch (err) {
      console.warn("Could not cache image to localStorage (likely quota exceeded):", err);
    }
  };
  reader.readAsDataURL(file);
}

analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  uploadSection.hidden = true;
  loadingSection.hidden = false;

  const formData = new FormData();
  formData.append('image', selectedFile);

  try {
    const res = await fetch('/api/analyze', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) throw new Error(data.error || 'Something went wrong');

    currentData = data;
    
    // Cache primary data in localStorage
    localStorage.setItem('prescriptosafe_data', JSON.stringify(data));
    
    renderResults(data);
  } catch (err) {
    alert('Analysis failed: ' + err.message);
    loadingSection.hidden = true;
    uploadSection.hidden = false;
  }
});

resetBtn.addEventListener('click', () => {
  selectedFile = null;
  currentData = null;
  previewImg.hidden = true;
  dropzoneContent.hidden = false;
  analyzeBtn.disabled = true;
  fileInput.value = '';
  resultsSection.hidden = true;
  uploadSection.hidden = false;
  uploadSection.style.display = 'block';
  canvasOverlay.innerHTML = '';
  loadingPreviewImg.src = '';
  
  // Clear session cache
  localStorage.removeItem('prescriptosafe_image');
  localStorage.removeItem('prescriptosafe_data');
  localStorage.removeItem('prescriptosafe_profile');
});

// Modal Logic
shareBtn.addEventListener('click', () => {
  shareModal.style.display = 'flex';
  shareModal.hidden = false;
  sharePhoneInput.value = '';
  shareStatus.hidden = true;
});

closeModal.addEventListener('click', () => {
  shareModal.style.display = 'none';
  shareModal.hidden = true;
});

window.addEventListener('click', (e) => {
  if (e.target === shareModal) {
    shareModal.style.display = 'none';
    shareModal.hidden = true;
  }
});

sendShareBtn.addEventListener('click', async () => {
  const phone = sharePhoneInput.value.trim();
  if (!phone) {
    alert("Please enter a valid phone number.");
    return;
  }
  
  sendShareBtn.disabled = true;
  sendShareBtn.textContent = "Sharing...";
  
  try {
    const res = await fetch('/api/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: phone,
        patient_name: patientNameInput.value,
        medications: currentData.medications,
        overall_severity: currentData.overall_severity
      })
    });
    const data = await res.json();
    
    shareStatus.hidden = false;
    if (data.sent_real) {
      shareStatus.className = "share-status";
      shareStatus.textContent = `✓ Safety report sent successfully to ${phone}!`;
    } else {
      shareStatus.className = "share-status";
      shareStatus.textContent = `[Simulation Mode]\nMessage content constructed:\n\n${data.message}`;
    }
  } catch (err) {
    alert("Sharing failed: " + err.message);
  } finally {
    sendShareBtn.disabled = false;
    sendShareBtn.textContent = "Send SMS";
  }
});

// Render results
function renderResults(data) {
  loadingSection.hidden = true;
  resultsSection.hidden = false;

  mockNotice.hidden = !data.using_mock_data;
  if (data.using_mock_data) {
    uploadSection.hidden = false;
    uploadSection.style.display = 'none';
  }

  // Populate patient metadata inputs default
  patientNameInput.value = data.patient_name || '';
  patientAgeInput.value = '';
  patientPregnancyInput.value = 'no';
  document.querySelectorAll('.condition-cb').forEach(cb => cb.checked = false);

  updateOverallBadge(data.overall_severity);
  drawBoundingBoxes(data.medications);
  buildMedsFormList(data.medications);
}

function updateOverallBadge(severity) {
  const badge = document.getElementById('overallBadge');
  badge.className = 'badge ' + severity;
  badge.textContent = { red: 'Needs review', yellow: 'Minor flags', green: 'Looks safe' }[severity];
}

// Bounding box draw
function drawBoundingBoxes(medications) {
  canvasOverlay.innerHTML = '';
  medications.forEach((med, index) => {
    if (med.box_2d && med.box_2d.length === 4) {
      const [ymin, xmin, ymax, xmax] = med.box_2d;
      
      const box = document.createElement('div');
      box.className = 'bbox-rect';
      box.id = `bbox-${index}`;
      box.style.top = `${ymin / 10}%`;
      box.style.left = `${xmin / 10}%`;
      box.style.width = `${(xmax - xmin) / 10}%`;
      box.style.height = `${(ymax - ymin) / 10}%`;
      box.title = med.canonical_name || med.drug_name || 'Medication';
      
      // Link selections
      box.addEventListener('mouseenter', () => highlightMedSelection(index));
      box.addEventListener('mouseleave', () => clearMedSelection(index));
      
      canvasOverlay.appendChild(box);
    }
  });
}

function highlightMedSelection(index) {
  const box = document.getElementById(`bbox-${index}`);
  const card = document.getElementById(`med-card-${index}`);
  if (box) box.classList.add('active');
  if (card) {
    card.classList.add('active');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function clearMedSelection(index) {
  const box = document.getElementById(`bbox-${index}`);
  const card = document.getElementById(`med-card-${index}`);
  if (box) box.classList.remove('active');
  if (card) card.classList.remove('active');
}

// Get SVG icon based on severity level
function getFlagIcon(level) {
  if (level === 'red') {
    return `<svg class="flag-dot" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-top: 2px;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
  } else if (level === 'yellow') {
    return `<svg class="flag-dot" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-top: 2px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
  } else {
    return `<svg class="flag-dot" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-top: 2px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
  }
}

// Build list of editable medication cards
function buildMedsFormList(medications) {
  medsFormList.innerHTML = medications.map((med, index) => {
    // Determine card left-border accent color based on flags
    const levels = med.flags.map(f => f.level);
    let cardColor = 'var(--green)'; // Default green
    if (levels.includes('red')) {
      cardColor = 'var(--red)';
    } else if (levels.includes('yellow')) {
      cardColor = 'var(--yellow)';
    } else if (levels.includes('grey') || med.fda_status !== 'found') {
      cardColor = '#94A3B8'; // Slate grey for not found
    }

    const alertsHTML = med.flags.map(f => `
      <div class="flag ${f.level}">
        ${getFlagIcon(f.level)}
        <span>${f.message}</span>
      </div>
    `).join('');

    const fdaHTML = med.fda_status === 'found' ? `
      <div class="fda-info-box">
        <div class="fda-header">
          <span class="fda-badge">FDA Verified</span>
          ${med.rxcui ? `<span class="rxcui-badge">RxCUI: ${med.rxcui}</span>` : ''}
          <span>${med.fda_generic_name ? med.fda_generic_name : ''}</span>
        </div>
        ${med.fda_boxed_warning ? `
          <div class="fda-boxed-warning">
            <strong>⚠️ FDA Boxed Warning</strong>
            <span>${med.fda_boxed_warning}</span>
          </div>
        ` : ''}
      </div>
    ` : `
      <div class="fda-info-box" style="background: #F8FAFC; border-color: var(--line); color: var(--grey);">
        <div class="fda-header" style="color: var(--grey); margin-bottom: 0;">
          <span class="fda-badge" style="background: #E2E8F0; color: var(--grey); border-color: #CBD5E1;">Not Found</span>
          ${med.rxcui ? `<span class="rxcui-badge">RxCUI: ${med.rxcui}</span>` : ''}
          <span>Checked locally</span>
        </div>
      </div>
    `;

    return `
      <div class="med-card-editable" id="med-card-${index}" style="border-left-color: ${cardColor};"
           onmouseenter="document.getElementById('bbox-${index}')?.classList.add('active')" 
           onmouseleave="document.getElementById('bbox-${index}')?.classList.remove('active')">
        
        <div class="med-grid-inputs">
          <div class="form-group">
            <label>Drug Name</label>
            <input type="text" class="med-input med-name-input" data-index="${index}" data-field="drug_name" value="${med.drug_name || ''}">
          </div>
          <div class="form-group">
            <label>Dose (mg)</label>
            <input type="number" class="med-input med-dose-input" data-index="${index}" data-field="dosage_amount" value="${med.dosage_amount || ''}" placeholder="mg">
          </div>
          <div class="form-group">
            <label>Times/Day</label>
            <input type="number" class="med-input med-freq-input" data-index="${index}" data-field="frequency_per_day" value="${med.frequency_per_day || ''}" placeholder="x">
          </div>
          <div class="form-group">
            <label>Days</label>
            <input type="number" class="med-input med-dur-input" data-index="${index}" data-field="duration_days" value="${med.duration_days || ''}" placeholder="days">
          </div>
        </div>
        
        <div class="med-raw" style="margin-bottom: 12px;">OCR reading: "${med.raw_text || ''}"</div>
        
        ${fdaHTML}
        
        <div class="flag-list" id="flags-container-${index}" style="margin-top: 16px;">
          ${alertsHTML}
        </div>
      </div>
    `;
  }).join('');

  // Register change listeners to run dynamic validation
  document.querySelectorAll('.med-input').forEach(input => {
    input.addEventListener('input', debounce(triggerValidation, 600));
  });
}

// Register listeners on patient profile form
[patientNameInput, patientAgeInput, patientPregnancyInput].forEach(elem => {
  elem.addEventListener('input', debounce(triggerValidation, 600));
  elem.addEventListener('change', debounce(triggerValidation, 600));
});

document.querySelectorAll('.condition-cb').forEach(cb => {
  cb.addEventListener('change', triggerValidation);
});

// Debounce helper
function debounce(func, delay) {
  let debounceTimer;
  return function() {
    const context = this;
    const args = arguments;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => func.apply(context, args), delay);
  };
}

// Trigger safety validation post-change
async function triggerValidation() {
  if (!currentData) return;
  
  // Scrape profile details
  const profile = {
    pregnancy: patientPregnancyInput.value,
    age: parseInt(patientAgeInput.value) || null,
    name: patientNameInput.value,
    conditions: Array.from(document.querySelectorAll('.condition-cb:checked')).map(cb => cb.value)
  };
  
  // Cache profile data in localStorage
  localStorage.setItem('prescriptosafe_profile', JSON.stringify(profile));
  
  // Scrape list of edited drugs
  const meds = [];
  const count = currentData.medications.length;
  for (let i = 0; i < count; i++) {
    const original = currentData.medications[i];
    
    // Find inputs
    const nameVal = document.querySelector(`.med-name-input[data-index="${i}"]`).value;
    const doseVal = parseInt(document.querySelector(`.med-dose-input[data-index="${i}"]`).value) || null;
    const freqVal = parseInt(document.querySelector(`.med-freq-input[data-index="${i}"]`).value) || null;
    const durVal = parseInt(document.querySelector(`.med-dur-input[data-index="${i}"]`).value) || null;
    
    meds.push({
      ...original,
      drug_name: nameVal,
      dosage_amount: doseVal,
      frequency_per_day: freqVal,
      duration_days: durVal
    });
  }
  
  if (validationLoader) {
    validationLoader.style.display = 'flex';
  }
  
  try {
    const res = await fetch('/api/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        medications: meds,
        patient_profile: profile
      })
    });
    const result = await res.json();
    
    if (res.ok) {
      // Update data cache
      currentData.medications = result.medications;
      currentData.overall_severity = result.overall_severity;
      
      // Cache data in localStorage
      localStorage.setItem('prescriptosafe_data', JSON.stringify(currentData));
      
      // Update safety badge
      updateOverallBadge(result.overall_severity);
      
      // Update individual drug flags UI and card borders
      result.medications.forEach((med, idx) => {
        const flagsContainer = document.getElementById(`flags-container-${idx}`);
        if (flagsContainer) {
          flagsContainer.innerHTML = med.flags.map(f => `
            <div class="flag ${f.level}">
              ${getFlagIcon(f.level)}
              <span>${f.message}</span>
            </div>
          `).join('');
        }

        // Update card left-border accent color dynamically
        const cardElement = document.getElementById(`med-card-${idx}`);
        if (cardElement) {
          const levels = med.flags.map(f => f.level);
          let cardColor = 'var(--green)';
          if (levels.includes('red')) {
            cardColor = 'var(--red)';
          } else if (levels.includes('yellow')) {
            cardColor = 'var(--yellow)';
          } else if (levels.includes('grey') || med.fda_status !== 'found') {
            cardColor = '#94A3B8';
          }
          cardElement.style.borderLeftColor = cardColor;
        }
      });
    }
  } catch (err) {
    console.error("Validation failed: ", err);
  } finally {
    if (validationLoader) {
      validationLoader.style.display = 'none';
    }
  }
}

// Session restore logic on page load
function restoreCachedSession() {
  const cachedImg = localStorage.getItem('prescriptosafe_image');
  const cachedData = localStorage.getItem('prescriptosafe_data');
  const cachedProfile = localStorage.getItem('prescriptosafe_profile');
  
  if (cachedImg) {
    previewImg.src = cachedImg;
    previewImg.hidden = false;
    dropzoneContent.hidden = true;
    resultsPreviewImg.src = cachedImg;
    loadingPreviewImg.src = cachedImg;
  }
  
  if (cachedData) {
    try {
      currentData = JSON.parse(cachedData);
      renderResults(currentData);
      
      // Show results dashboard, hide upload screen
      uploadSection.hidden = true;
      uploadSection.style.display = 'none';
      
      // Load profile inputs after rendering (since renderResults resets them)
      if (cachedProfile) {
        const profile = JSON.parse(cachedProfile);
        patientNameInput.value = profile.name || '';
        patientAgeInput.value = profile.age || '';
        patientPregnancyInput.value = profile.pregnancy || 'no';
        
        if (profile.conditions) {
          document.querySelectorAll('.condition-cb').forEach(cb => {
            cb.checked = profile.conditions.includes(cb.value);
          });
        }
      }
      
      // Trigger validation to ensure warnings and badges are rendered immediately for the restored session
      triggerValidation();
    } catch (err) {
      console.error("Failed to restore cached session data:", err);
    }
  }
}

// Register initialization on DOM ready
window.addEventListener('DOMContentLoaded', restoreCachedSession);
