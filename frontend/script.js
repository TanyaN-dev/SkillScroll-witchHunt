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
    statusIndicator.textContent = "ಸಂಪರ್ಕಿಸಲಾಗುತ್ತಿದೆ... (Connecting)";
    disablePttBtn();
    
    playInitialGreeting(questId);
}

async function playInitialGreeting(questId) {
    statusIndicator.textContent = "ಆಲೋಚಿಸುತ್ತಿದೆ... (Thinking)";
    statusIndicator.style.color = "var(--text-muted)";
    
    try {
        const response = await fetch(`/start_negotiation?quest_id=${questId}`);
        if (!response.ok) throw new Error("Failed to start negotiation");
        
        const data = await response.json();
        
        conversationHistory.push({role: "model", parts: [{text: data.text}]});
        addBubble(data.text, "agent");
        
        statusIndicator.textContent = "ವ್ಯಾಪಾರಿ ಮಾತನಾಡುತ್ತಿದ್ದಾರೆ... (Speaking)";
        statusIndicator.style.color = "var(--success)";
        
        // Ensure Kannada Voice
        const utterance = new SpeechSynthesisUtterance(data.text);
        utterance.lang = 'kn-IN';
        
        utterance.onend = () => {
            statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ (Hold to Talk)";
            statusIndicator.style.color = "var(--text-muted)";
            enablePttBtn();
        };
        
        window.speechSynthesis.speak(utterance);

    } catch (err) {
        console.error(err);
        statusIndicator.textContent = "Error loading greeting.";
        enablePttBtn();
    }
}

function closeNegotiation() {
    overlay.classList.remove('active');
    if (isRecording) {
        stopRecording(false);
    }
    window.speechSynthesis.cancel();
    enablePttBtn();
}

pttBtn.addEventListener('mousedown', startRecording);
pttBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });

pttBtn.addEventListener('mouseup', () => stopRecording(true));
pttBtn.addEventListener('mouseleave', () => { if(isRecording) stopRecording(true); });
pttBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(true); });

async function startRecording() {
    if (isRecording) return;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
        mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
        audioChunks = [];

        mediaRecorder.ondataavailable = e => {
            if (e.data && e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        mediaRecorder.start();
        isRecording = true;
        pttBtn.classList.add('recording');
        statusIndicator.textContent = "ಆಲಿಸುತ್ತಿದೆ... (Listening)";
        statusIndicator.style.color = "var(--primary)";

    } catch (err) {
        console.error("Mic error:", err);
        statusIndicator.textContent = "Mic access denied.";
    }
}

function stopRecording(sendData) {
    if (!isRecording) return;
    isRecording = false;
    pttBtn.classList.remove('recording');
    
    if (sendData) {
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            mediaRecorder.stream.getTracks().forEach(track => track.stop());

            if (audioBlob.size < 1000) {
                alert("Please hold the button longer and speak clearly.");
                statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ (Hold to Talk)";
                statusIndicator.style.color = "var(--text-muted)";
                return;
            }

            statusIndicator.textContent = "ಆಲೋಚಿಸುತ್ತಿದೆ... (Thinking)";
            statusIndicator.style.color = "var(--text-muted)";
            await sendAudioToBackend(audioBlob);
        };
        mediaRecorder.stop();
    } else {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
        statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ (Hold to Talk)";
    }
}

function addBubble(text, sender) {
    const bubble = document.createElement('div');
    bubble.className = `bubble ${sender}`;
    bubble.textContent = text;
    chatArea.appendChild(bubble);
    chatArea.scrollTop = chatArea.scrollHeight;
}

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
            alert(data.detail || "Error connecting to AI.");
            statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ (Hold to Talk)";
            statusIndicator.style.color = "var(--text-muted)";
            return;
        }
        
        conversationHistory.push({role: "user", parts: [{text: data.user_text}]});
        conversationHistory.push({role: "model", parts: [{text: data.text}]});
        turnCount++;
        
        addBubble(data.user_text, "user");
        addBubble(data.text, "agent");
        
        statusIndicator.textContent = "ವ್ಯಾಪಾರಿ ಮಾತನಾಡುತ್ತಿದ್ದಾರೆ... (Speaking)";
        statusIndicator.style.color = "var(--success)";
        
        const utterance = new SpeechSynthesisUtterance(data.text);
        utterance.lang = 'kn-IN';
        
        utterance.onend = () => {
            statusIndicator.textContent = "ಮೈಕ್ ಬಟನ್ ಒತ್ತಿ ಮಾತನಾಡಿ (Hold to Talk)";
            statusIndicator.style.color = "var(--text-muted)";
            enablePttBtn();
            
            // Trigger feedback after 3 turns for the demo to save time
            if (turnCount >= 3) {
                setTimeout(() => showFeedback(data.confidence, data.feedback), 1000);
            }
        };
        
        disablePttBtn();
        window.speechSynthesis.speak(utterance);

    } catch (err) {
        console.error("Backend error:", err);
        statusIndicator.textContent = "Error occurred.";
        enablePttBtn();
    }
}

function showFeedback(score, aiFeedbackText) {
    // Populate the new AI feedback section
    document.getElementById('aiFeedbackText').textContent = aiFeedbackText;
    document.getElementById('confidenceScore').textContent = score;
    
    feedbackModal.classList.add('active');
    
    setTimeout(() => {
        document.getElementById('meterFill').style.width = `${score}%`;
        let currentW = parseInt(xpBar.style.width || "30");
        xpBar.style.width = Math.min(100, currentW + 10) + "%";
    }, 100);
}

function closeFeedback() {
    feedbackModal.classList.remove('active');
    document.getElementById('meterFill').style.width = '0%';
}

function shareToWhatsApp() {
    const text = encodeURIComponent("I just practiced negotiation in SkillScroll and got a great score! Try it out!");
    window.open(`https://wa.me/?text=${text}`, '_blank');
}