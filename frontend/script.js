let voices = [];

// Load voices properly
function loadVoices() {
    voices = window.speechSynthesis.getVoices();
}
window.speechSynthesis.onvoiceschanged = loadVoices;
loadVoices(); // Initial load

// Global Variables
let currentQuestId = null;
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let turnCount = 0;
let conversationHistory = [];

// DOM Elements
const overlay = document.getElementById('negotiationOverlay');
const chatArea = document.getElementById('chatArea');
const pttBtn = document.getElementById('pttBtn');
const statusIndicator = document.getElementById('statusIndicator');
const activeQuestTitle = document.getElementById('activeQuestTitle');
const feedbackModal = document.getElementById('feedbackModal');
const xpBar = document.getElementById('xpBar');

function disablePttBtn() {
    pttBtn.disabled = true;
    pttBtn.style.opacity = '0.5';
    pttBtn.style.pointerEvents = 'none';
}

function enablePttBtn() {
    pttBtn.disabled = false;
    pttBtn.style.opacity = '1';
    pttBtn.style.pointerEvents = 'auto';
}

function openNegotiation(questId, title) {
    currentQuestId = questId;
    activeQuestTitle.textContent = title;
    turnCount = 0;
    conversationHistory = [];
   
    chatArea.innerHTML = '';
    overlay.classList.add('active');
   
    statusIndicator.textContent = "ಸಂಪರ್ಕಿಸಲಾಗುತ್ತಿದೆ...";
    disablePttBtn();
   
    playInitialGreeting(questId);
}

async function playInitialGreeting(questId) {
    statusIndicator.textContent = "ಆಲೋಚಿಸುತ್ತಿದೆ...";
   
    try {
        const response = await fetch(`/start_negotiation?quest_id=${questId}`);
        if (!response.ok) throw new Error("Failed");
        
        const data = await response.json();
       
        conversationHistory.push({role: "model", parts: [{text: data.text}]});
        addBubble(data.text, "agent");
        
        speakKannada(data.text, () => {
            statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ";
            enablePttBtn();
        });
    } catch (err) {
        console.error(err);
        statusIndicator.textContent = "Error loading greeting.";
        enablePttBtn();
    }
}

// Improved Speech Function
function speakKannada(text, onEndCallback = null) {
    window.speechSynthesis.cancel();
   
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'kn-IN';
    utterance.rate = 0.92;
    utterance.pitch = 1.0;

    if (voices.length > 0) {
        const bestVoice = voices.find(v =>
            v.lang.includes('kn') || 
            v.name.toLowerCase().includes('kannada') ||
            v.name.toLowerCase().includes('indian')
        );
        if (bestVoice) utterance.voice = bestVoice;
    }

    utterance.onend = () => {
        if (onEndCallback) onEndCallback();
    };
    window.speechSynthesis.speak(utterance);
}

function closeNegotiation() {
    overlay.classList.remove('active');
    window.speechSynthesis.cancel();
    if (isRecording) stopRecording(false);
    enablePttBtn();
}

// ====================== IMPROVED RECORDING LOGIC ======================
pttBtn.addEventListener('mousedown', startRecording);
pttBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });

pttBtn.addEventListener('mouseup', () => stopRecording(true));
pttBtn.addEventListener('mouseleave', () => { if (isRecording) stopRecording(true); });
pttBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(true); });

async function startRecording() {
    if (isRecording) return;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: { 
                echoCancellation: true,
                noiseSuppression: true
            } 
        });

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
            ? 'audio/webm;codecs=opus' 
            : 'audio/webm';

        mediaRecorder = new MediaRecorder(stream, { mimeType });
        audioChunks = [];

        mediaRecorder.ondataavailable = e => {
            if (e.data && e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        mediaRecorder.start(300);   // Record in small chunks - better for mobile
        isRecording = true;
        pttBtn.classList.add('recording');
        statusIndicator.textContent = "ಆಲಿಸುತ್ತಿದೆ... 🎤";
        statusIndicator.style.color = "var(--primary)";

    } catch (err) {
        console.error("Mic Error:", err);
        statusIndicator.textContent = "ಮೈಕ್ ಅನುಮತಿ ನೀಡಿ";
    }
}

function stopRecording(sendData) {
    if (!isRecording || !mediaRecorder) return;

    isRecording = false;
    pttBtn.classList.remove('recording');

    if (sendData) {
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            console.log("🎤 Audio Recorded Size:", audioBlob.size, "bytes");

            mediaRecorder.stream.getTracks().forEach(track => track.stop());

            if (audioBlob.size < 1500) {
                statusIndicator.textContent = "ದಯವಿಟ್ಟು 4-5 ಸೆಕೆಂಡ್ ಮಾತನಾಡಿ";
                enablePttBtn();
                return;
            }

            statusIndicator.textContent = "ಆಲೋಚಿಸುತ್ತಿದೆ...";
            await sendAudioToBackend(audioBlob);
        };
        mediaRecorder.stop();
    } else {
        if (mediaRecorder.stream) {
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    }
}

// ====================== Backend Call ======================
async function sendAudioToBackend(audioBlob) {
    const formData = new FormData();
    formData.append("quest_id", currentQuestId);
    formData.append("history", JSON.stringify(conversationHistory));
    formData.append("audio", audioBlob, "audio.webm");

    try {
        const response = await fetch('/negotiate', { 
            method: 'POST', 
            body: formData 
        });
        
        const data = await response.json();

        if (!response.ok) {
            alert(data.detail || "Server error");
            enablePttBtn();
            return;
        }

        conversationHistory.push({role: "user", parts: [{text: data.user_text}]});
        conversationHistory.push({role: "model", parts: [{text: data.text}]});
        turnCount++;

        addBubble(data.user_text, "user");
        addBubble(data.text, "agent");

        speakKannada(data.text, () => {
            statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ";
            enablePttBtn();

            if (turnCount >= 3) {
                setTimeout(() => showFeedback(data.confidence, data.feedback), 800);
            }
        });

    } catch (err) {
        console.error("Backend error:", err);
        statusIndicator.textContent = "Error occurred";
        enablePttBtn();
    }
}

function addBubble(text, sender) {
    const bubble = document.createElement('div');
    bubble.className = `bubble ${sender}`;
    bubble.textContent = text;
    chatArea.appendChild(bubble);
    chatArea.scrollTop = chatArea.scrollHeight;
}

function showFeedback(score, aiFeedbackText) {
    document.getElementById('aiFeedbackText').textContent = aiFeedbackText;
    document.getElementById('confidenceScore').textContent = score;
    feedbackModal.classList.add('active');
   
    setTimeout(() => {
        document.getElementById('meterFill').style.width = `${score}%`;
        let current = parseInt(xpBar.style.width || "30");
        xpBar.style.width = Math.min(100, current + 10) + "%";
    }, 100);
}

function closeFeedback() {
    feedbackModal.classList.remove('active');
}
