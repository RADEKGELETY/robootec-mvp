const stopAll = () => {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  document.querySelectorAll("[data-speak]").forEach((button) => {
    button.classList.remove("is-speaking");
    button.textContent = "Zapnout zvuk";
  });
};

const pickVoice = () => {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;
  return (
    voices.find((voice) => voice.lang.toLowerCase().startsWith("cs")) || voices[0]
  );
};

const speak = (text, button) => {
  if (!("speechSynthesis" in window)) {
    window.alert("Tento prohlížeč nepodporuje hlasový výstup.");
    return;
  }
  stopAll();
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  utterance.lang = voice?.lang || "cs-CZ";
  utterance.rate = 0.97;
  utterance.pitch = 1;
  if (voice) utterance.voice = voice;
  utterance.onstart = () => {
    button.classList.add("is-speaking");
    button.textContent = "Vypnout zvuk";
  };
  utterance.onend = () => {
    button.classList.remove("is-speaking");
    button.textContent = "Zapnout zvuk";
  };
  utterance.onerror = () => {
    button.classList.remove("is-speaking");
    button.textContent = "Zapnout zvuk";
  };
  window.speechSynthesis.speak(utterance);
};

document.addEventListener("DOMContentLoaded", () => {
  const speakButton = document.querySelector("[data-speak]");
  if (!speakButton) return;
  const speechText = speakButton.getAttribute("data-speech") || "";

  speakButton.addEventListener("click", () => {
    if (speakButton.classList.contains("is-speaking")) {
      stopAll();
      return;
    }
    speak(speechText, speakButton);
  });

  if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices();
    };
  }
});
