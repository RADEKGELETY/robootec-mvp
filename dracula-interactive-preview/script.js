const introOverlay = document.getElementById('introOverlay');
const enterBtn = document.getElementById('enterBtn');
const toggleSoundBtn = document.getElementById('toggleSound');
const toggleVoicesBtn = document.getElementById('toggleVoices');
const chapters = Array.from(document.querySelectorAll('.chapter'));
const navLinks = Array.from(document.querySelectorAll('.nav-link'));
const teaserPanel = document.getElementById('teaserPanel');
const openTeaser = document.getElementById('openTeaser');

let audioUnlocked = false;
let soundEnabled = false;
let voicesEnabled = false;
let audioCtx;
let masterGain;
let droneState;
let availableVoices = [];

const maleHints = [
  'male',
  'man',
  'muz',
  'muž',
  'martin',
  'jakub',
  'petr',
  'jan',
  'jiri',
  'david',
  'tomas',
  'alek',
  'ales',
  'google',
  'microsoft',
];
const femaleHints = ['female', 'woman', 'zena', 'žena', 'eva', 'jana', 'anna', 'lucie', 'sara', 'petra'];

const trackSettings = {
  karpaty: { base: 55, filter: 240, gain: 0.08 },
  zpoved: { base: 50, filter: 180, gain: 0.07 },
  detstvi: { base: 65, filter: 320, gain: 0.06 },
  rukojmi: { base: 42, filter: 150, gain: 0.08 },
};

function buildDrone() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  masterGain = audioCtx.createGain();
  masterGain.gain.value = 0.0;
  masterGain.connect(audioCtx.destination);

  const osc1 = audioCtx.createOscillator();
  const osc2 = audioCtx.createOscillator();
  const filter = audioCtx.createBiquadFilter();
  const lfo = audioCtx.createOscillator();
  const lfoGain = audioCtx.createGain();

  osc1.type = 'sawtooth';
  osc2.type = 'triangle';
  filter.type = 'lowpass';
  filter.Q.value = 1.2;

  lfo.frequency.value = 0.08;
  lfoGain.gain.value = 50;

  lfo.connect(lfoGain);
  lfoGain.connect(filter.frequency);

  osc1.connect(filter);
  osc2.connect(filter);
  filter.connect(masterGain);

  osc1.start();
  osc2.start();
  lfo.start();

  droneState = { osc1, osc2, filter };
}

function applyTrack(name) {
  if (!droneState) return;
  const settings = trackSettings[name] || trackSettings.karpaty;
  droneState.osc1.frequency.setTargetAtTime(settings.base, audioCtx.currentTime, 0.6);
  droneState.osc2.frequency.setTargetAtTime(settings.base * 1.5, audioCtx.currentTime, 0.6);
  droneState.filter.frequency.setTargetAtTime(settings.filter, audioCtx.currentTime, 0.6);
  if (soundEnabled) {
    masterGain.gain.setTargetAtTime(settings.gain, audioCtx.currentTime, 0.8);
  }
}

function unlockAudio() {
  if (audioUnlocked) return;
  buildDrone();
  audioUnlocked = true;
  soundEnabled = true;
  masterGain.gain.setTargetAtTime(trackSettings.karpaty.gain, audioCtx.currentTime, 0.8);
  updateSoundLabel();
}

function updateSoundLabel() {
  toggleSoundBtn.textContent = `Soundtrack: ${soundEnabled ? 'Zapnuto' : 'Vypnuto'}`;
}

function updateVoicesLabel() {
  toggleVoicesBtn.textContent = `Hlasy: ${voicesEnabled ? 'Zapnuto' : 'Vypnuto'}`;
}

function loadVoices() {
  availableVoices = window.speechSynthesis.getVoices();
}

window.speechSynthesis.onvoiceschanged = loadVoices;
loadVoices();

function scoreVoice(voice, role) {
  let score = 0;
  const name = (voice.name || '').toLowerCase();
  if (voice.lang && voice.lang.startsWith('cs')) score += 5;
  if (maleHints.some((hint) => name.includes(hint))) score += 3;
  if (femaleHints.some((hint) => name.includes(hint))) score -= 2;
  if (name.includes('deep') || name.includes('bass') || name.includes('baritone')) score += 2;
  if (name.includes('google') || name.includes('microsoft')) score += 1;
  if (role === 'dialogue') score -= 1;
  return score;
}

function getVoice(role) {
  if (!availableVoices.length) return null;
  const ranked = [...availableVoices].sort((a, b) => scoreVoice(b, role) - scoreVoice(a, role));
  const map = {
    narrator: 0,
    radu: 1,
    oldman: 2,
    dialogue: 2,
  };
  const index = map[role] ?? 0;
  return ranked[index % ranked.length];
}

function speakChapter(chapterEl) {
  if (!voicesEnabled) {
    voicesEnabled = true;
    updateVoicesLabel();
  }
  const spans = chapterEl.querySelectorAll('[data-voice]');
  if (!spans.length) return;
  window.speechSynthesis.cancel();
  spans.forEach((span) => {
    const text = span.textContent.trim();
    if (!text) return;
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = getVoice(span.dataset.voice);
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    } else {
      utterance.lang = 'cs-CZ';
    }
    utterance.volume = 1;
    if (span.dataset.voice === 'narrator') {
      utterance.rate = 0.8;
      utterance.pitch = 0.68;
    } else if (span.dataset.voice === 'dialogue') {
      utterance.rate = 0.9;
      utterance.pitch = 0.9;
    } else {
      utterance.rate = 0.85;
      utterance.pitch = 0.78;
    }
    window.speechSynthesis.speak(utterance);
  });
}

function pauseSpeech() {
  window.speechSynthesis.cancel();
}

enterBtn.addEventListener('click', () => {
  introOverlay.classList.add('hidden');
  introOverlay.setAttribute('aria-hidden', 'true');
  unlockAudio();
  voicesEnabled = true;
  updateVoicesLabel();
});

toggleSoundBtn.addEventListener('click', () => {
  if (!audioUnlocked) {
    unlockAudio();
  }
  soundEnabled = !soundEnabled;
  if (soundEnabled) {
    const current = document.querySelector('.chapter.active');
    const trackName = current?.dataset.soundtrack || 'karpaty';
    applyTrack(trackName);
  } else {
    masterGain.gain.setTargetAtTime(0.0, audioCtx.currentTime, 0.4);
  }
  updateSoundLabel();
});

toggleVoicesBtn.addEventListener('click', () => {
  voicesEnabled = !voicesEnabled;
  updateVoicesLabel();
  if (!voicesEnabled) {
    pauseSpeech();
  }
});

chapters.forEach((chapter) => {
  chapter.querySelectorAll('[data-action="play"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      speakChapter(chapter);
    });
  });
  chapter.querySelectorAll('[data-action="pause"]').forEach((btn) => {
    btn.addEventListener('click', pauseSpeech);
  });
});

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        chapters.forEach((ch) => ch.classList.remove('active'));
        entry.target.classList.add('active');
        const trackName = entry.target.dataset.soundtrack || 'karpaty';
        if (audioUnlocked && soundEnabled) {
          applyTrack(trackName);
        }
        navLinks.forEach((link) => link.classList.remove('active'));
        const activeLink = navLinks.find((link) => link.getAttribute('href') === `#${entry.target.id}`);
        if (activeLink) activeLink.classList.add('active');
      }
    });
  },
  { threshold: 0.4 }
);

chapters.forEach((chapter) => observer.observe(chapter));

openTeaser.addEventListener('click', () => {
  teaserPanel.classList.toggle('teaser-active');
  teaserPanel.querySelector('.video-sub').textContent = teaserPanel.classList.contains('teaser-active')
    ? 'Teaser je připraven — vložit reálné video.'
    : 'Krátký vizuální sestřih (placeholder)';
});

updateSoundLabel();
updateVoicesLabel();
