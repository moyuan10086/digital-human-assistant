<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue';
import DigitalHuman from '../components/DigitalHuman.vue';
import { 
  ChatBubbleLeftRightIcon,
  PencilSquareIcon,
  CameraIcon,
  BookOpenIcon,
  LanguageIcon,
  VideoCameraIcon,
  QuestionMarkCircleIcon,
  PhoneIcon,
  UserIcon,
  XMarkIcon,
  MicrophoneIcon,
  StopIcon, 
  SpeakerWaveIcon,
  PaperAirplaneIcon,
  PlusIcon
} from '@heroicons/vue/24/solid';

import { showToast } from 'vant';
import 'vant/es/toast/style';

// Markdown Support
import MarkdownIt from 'markdown-it';

// Types
interface Message {
  id: number;
  type: 'ai' | 'user';
  contentType?: 'text' | 'audio';
  text: string;
  audioUrl?: string;
  audioDuration?: number;
  isPlaying?: boolean;
}

interface AppItem {
  name: string;
  icon: any;
  color: string;
  action?: string;
}

// Refs
const digitalHumanRef = ref<InstanceType<typeof DigitalHuman> | null>(null);
const chatContainerRef = ref<HTMLDivElement | null>(null);
const isAppsPanelOpen = ref(false);
const isEditMode = ref(false);
const userInput = ref('');
const voiceInput = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const inputMode = ref<'text' | 'voice'>('text');
const isPhoneMode = ref(false);
const isPhoneActive = ref(false);
const phoneStatus = ref('点击通话');
const sessionId = ref<string>('');
const userAvatarUrl = ref<string>('');
const userAvatarFileInput = ref<HTMLInputElement | null>(null);
const showConversationList = ref(false);
const conversations = ref<any[]>([]);

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
});

const renderMarkdown = (text: string) => {
  if (!text) return '';
  return md.render(text);
};

const cleanTextForSpeech = (text: string) => {
  if (!text) return '';
  const html = md.render(text);
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = html;
  let plainText = tempDiv.innerText;
  const emojiRegex = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2300}-\u{23FF}\u{2B50}\u{2B55}\u{2934}\u{2935}\u{2B05}-\u{2B07}\u{2194}-\u{21AA}\u{200D}\u{FE0F}]/gu;
  plainText = plainText.replace(emojiRegex, '');
  plainText = plainText.replace(/[*#`_~>]/g, '');
  return plainText.trim();
};

// Settings State (Read-only or loaded from history)
const isWebSearchEnabled = ref(true); // Default, maybe sync later?
const isVoiceReplyEnabled = ref(true);
const avatarFit = ref<'cover' | 'contain'>('cover');
const avatarScale = ref<number>(1.0);
const ttsProvider = ref<'microsoft' | 'volcengine'>('microsoft');
const volcVoice = ref('zh_female_vv_jupiter_bigtts'); // For traditional TTS
const phoneVoice = ref('zh_female_vv_jupiter_bigtts'); // For realtime phone mode
const currentAvatarUrl = ref<string>('');
const aiAvatarUrl = ref<string>('/src/assets/vue.svg'); // AI message avatar

// Auto-resize textarea
watch(userInput, async () => {
  if (inputMode.value === 'voice') return; 
  await nextTick();
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto';
    textareaRef.value.style.height = textareaRef.value.scrollHeight + 'px';
  }
});

const isAiThinking = ref(false);
const isAvatarSpeaking = ref(false);
watch(isAvatarSpeaking, (newVal) => {
    if (!newVal) {
        messages.value.forEach(msg => msg.isPlaying = false);
    }
});
const messages = ref<Message[]>([
  { id: 1, type: 'ai', text: '您好！我是您的AI助教，有什么可以帮助您的吗？' }
]);

// Auto-scroll to bottom when messages change
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
    }
  });
};

watch(messages, () => {
  scrollToBottom();
}, { deep: true });

// Apps Data - Removed Settings
const apps: AppItem[] = [
  { name: '智能问答', icon: ChatBubbleLeftRightIcon, color: 'from-blue-400 to-blue-500' },
  { name: '作业批改', icon: PencilSquareIcon, color: 'from-emerald-300 to-emerald-400' },
  { name: '图像识别', icon: CameraIcon, color: 'from-indigo-400 to-indigo-500' },
  { name: '指题辅导', icon: BookOpenIcon, color: 'from-orange-300 to-orange-400' },
  { name: '英语对练', icon: LanguageIcon, color: 'from-teal-300 to-teal-400' },
  { name: '图生视频', icon: VideoCameraIcon, color: 'from-pink-300 to-pink-400' },
  { name: '常见问题', icon: QuestionMarkCircleIcon, color: 'from-sky-300 to-sky-400' },
];

// Methods
const playAudio = (url?: string) => {
  if (!url) return;
  const audio = new Audio(url);
  audio.play();
};

const handleAppClick = (app: AppItem) => {
  if (app.name === '智能问答') {
    isAppsPanelOpen.value = false;
    nextTick(() => {
        const input = document.querySelector('textarea') as HTMLTextAreaElement;
        if (input) input.focus();
    });
  } else {
    showToast(`${app.name} 功能开发中`);
  }
};

const toggleSpeech = async (msg: Message) => {
    if (!digitalHumanRef.value) return;
    if (msg.isPlaying) {
        digitalHumanRef.value.stopSpeak();
        msg.isPlaying = false;
        isAvatarSpeaking.value = false;
        return;
    }
    if (isAvatarSpeaking.value) {
        digitalHumanRef.value.stopSpeak();
        messages.value.forEach(m => m.isPlaying = false);
    }
    const spokenText = cleanTextForSpeech(msg.text);
    try {
        msg.isPlaying = true; 
        isAvatarSpeaking.value = true;
        await digitalHumanRef.value.speak(spokenText);
    } catch (e) {
        console.error("Manual speak error:", e);
        msg.isPlaying = false;
        isAvatarSpeaking.value = false;
    }
};

interface AvatarItem {
  url: string;
  meta?: {
    fit?: 'cover' | 'contain';
    scale?: number;
  };
}

const avatarHistory = ref<AvatarItem[]>([]);

// Initialize history from Backend to set initial state
const loadHistory = async () => {
    try {
        const response = await fetch(`/history?t=${Date.now()}`);
        if (response.ok) {
            const data = await response.json();
            avatarHistory.value = data;

            if (data.length > 0) {
                const topItem = data[0];
                const topUrl = typeof topItem === 'string' ? topItem : topItem.url;

                if (!currentAvatarUrl.value || currentAvatarUrl.value !== topUrl) {
                     if (!currentAvatarUrl.value) {
                         selectAvatar(topItem);
                     }
                }
            }
        }
    } catch (e) {
        console.error("Failed to load history from backend", e);
    }
};

// Poll for history updates (in case Admin changed something)
const pollHistory = async () => {
    setInterval(async () => {
        try {
            const response = await fetch(`/history?t=${Date.now()}`);
            if (response.ok) {
                const newHistory = await response.json();
                
                // Always follow the latest history (Index 0 is the most recently used/modified)
                if (newHistory.length > 0) {
                    const topItem = newHistory[0];
                    const topUrl = typeof topItem === 'string' ? topItem : topItem.url;

                    if (topUrl !== currentAvatarUrl.value) {
                        console.log("Remote active avatar changed, switching...");
                        selectAvatar(topItem);
                    } else {
                        const meta = typeof topItem === 'string' ? {} : (topItem.meta || {});

                        if (meta.fit && meta.fit !== avatarFit.value) {
                            avatarFit.value = meta.fit;
                        }
                        if (meta.scale !== undefined && meta.scale !== avatarScale.value) {
                            avatarScale.value = meta.scale;
                        }

                        if (meta.ttsProvider && meta.ttsProvider !== ttsProvider.value) {
                            ttsProvider.value = meta.ttsProvider;
                        }
                        if (meta.volcVoice && meta.volcVoice !== volcVoice.value) {
                            volcVoice.value = meta.volcVoice;
                        }
                        if (meta.phoneVoice && meta.phoneVoice !== phoneVoice.value) {
                            phoneVoice.value = meta.phoneVoice;
                        }
                        if (meta.isWebSearchEnabled !== undefined && meta.isWebSearchEnabled !== isWebSearchEnabled.value) {
                            isWebSearchEnabled.value = meta.isWebSearchEnabled;
                        }
                        if (meta.isVoiceReplyEnabled !== undefined && meta.isVoiceReplyEnabled !== isVoiceReplyEnabled.value) {
                            isVoiceReplyEnabled.value = meta.isVoiceReplyEnabled;
                        }
                    }
                }
                
                avatarHistory.value = newHistory;
            }
        } catch (e) {
        }
    }, 5000);
};

// Load user avatar from localStorage
const loadUserAvatar = () => {
    const savedAvatar = localStorage.getItem('userAvatarUrl');
    if (savedAvatar) {
        userAvatarUrl.value = savedAvatar;
    }
};

// Load AI avatar from backend config
const loadAiAvatar = async () => {
    try {
        const response = await fetch('/config');
        if (response.ok) {
            const config = await response.json();
            if (config.aiAvatarUrl) {
                aiAvatarUrl.value = config.aiAvatarUrl;
            }
        }
    } catch (e) {
        console.error("Failed to load AI avatar config", e);
    }
};

// Load conversation history
const loadConversationHistory = async (convId: string) => {
    try {
        const response = await fetch(`/api/conversations/${convId}/messages`);
        if (response.ok) {
            const history = await response.json();
            // Clear current messages and load history
            messages.value = history.map((msg: any, index: number) => ({
                id: index + 1,
                type: msg.role === 'user' ? 'user' : 'ai',
                text: msg.content
            }));
            console.log('[Phone] Loaded conversation history:', messages.value.length, 'messages');
        }
    } catch (e) {
        console.error("Failed to load conversation history", e);
    }
};

// Load conversations list
const loadConversations = async () => {
    try {
        const response = await fetch('/api/conversations');
        if (response.ok) {
            conversations.value = await response.json();
        }
    } catch (e) {
        console.error("Failed to load conversations", e);
    }
};

// Select and load a conversation
const selectConversation = async (conv: any) => {
    sessionId.value = conv.id;
    await loadConversationHistory(conv.id);
    showConversationList.value = false;
    showToast(`已加载对话: ${conv.title || '新对话'}`);
};

// Create new conversation
const createNewConversation = () => {
    sessionId.value = '';
    messages.value = [{ id: 1, type: 'ai', text: '您好！我是您的AI助教，有什么可以帮助您的吗？' }];
    showConversationList.value = false;
    showToast('已创建新对话');
};

// Handle user avatar upload
const handleUserAvatarUpload = async (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload_user_avatar', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            userAvatarUrl.value = result.url;
            localStorage.setItem('userAvatarUrl', result.url);
            showToast('头像上传成功');
        } else {
            const err = await response.json();
            showToast(`上传失败: ${err.message}`);
        }
    } catch (e) {
        console.error("Upload user avatar error", e);
        showToast('上传出错');
    } finally {
        input.value = '';
    }
};

onMounted(() => {
    loadHistory();
    pollHistory();
    loadUserAvatar();
    loadAiAvatar();
});

const selectAvatar = (item: AvatarItem | string) => {
    const url = typeof item === 'string' ? item : item.url;
    const meta = typeof item === 'string' ? {} : (item.meta || {});

    if (digitalHumanRef.value) {
        digitalHumanRef.value.loadAvatarFromUrl(url);
        if (meta.fit) avatarFit.value = meta.fit;
        if (meta.scale !== undefined) avatarScale.value = meta.scale;
        if (meta.phoneVoice) phoneVoice.value = meta.phoneVoice;
    }
};

// Phone Call Logic
let phoneWs: WebSocket | null = null;
let currentUserMessage = '';
let currentAiMessage = '';
let currentQuestionId = '';
let lipSyncStopTimer: number | null = null;

// Handle Volcengine Realtime Events
const handlePhoneEvent = (data: any) => {
    console.log('Phone Event Detail:', data);

    // Handle conversation initialization
    if (data.type === 'conversation_init' && data.conversation_id) {
        const receivedConvId = data.conversation_id;
        console.log('[Phone] Conversation ID received:', receivedConvId);

        // Only load history if we're continuing an existing conversation
        // If sessionId was already set (user selected a conversation), keep it
        // If sessionId was empty (new conversation), use the new one but don't load history
        const shouldLoadHistory = sessionId.value === receivedConvId;
        sessionId.value = receivedConvId;

        if (shouldLoadHistory) {
            console.log('[Phone] Loading conversation history');
            loadConversationHistory(sessionId.value);
        } else {
            console.log('[Phone] Starting new conversation, not loading history');
        }
        return;
    }

    // Event 451: ASR Response (User speech recognition)
    if (data.results && Array.isArray(data.results)) {
        const result = data.results[0];
        if (result && result.text) {
            // Only show final result (not interim)
            if (!result.is_interim) {
                currentUserMessage = result.text;
                // Update or add user message
                const lastMsg = messages.value[messages.value.length - 1];
                if (lastMsg && lastMsg.type === 'user' && lastMsg.id === -1) {
                    lastMsg.text = currentUserMessage;
                } else {
                    messages.value.push({
                        id: -1,
                        type: 'user',
                        text: currentUserMessage
                    });
                }
            }
        }
    }

    // Event 350: TTS Sentence Start (AI starts speaking)
    if (data.tts_type && data.question_id && data.reply_id) {
        console.log('[Home] Event 350 detected - TTS Start');
        console.log('[Home] digitalHumanRef:', digitalHumanRef.value);
        // Start digital human lip sync animation
        if (digitalHumanRef.value) {
            console.log('[Home] Calling startExternalAudioSync');
            digitalHumanRef.value.startExternalAudioSync();
        } else {
            console.warn('[Home] digitalHumanRef is null!');
        }
    }

    // Event 550: Chat Response (AI reply text)
    if (data.content !== undefined && data.question_id && data.reply_id) {
        currentAiMessage += data.content;
        currentQuestionId = data.question_id;

        // Update or add AI message (accumulate content)
        const lastMsg = messages.value[messages.value.length - 1];
        if (lastMsg && lastMsg.type === 'ai' && lastMsg.id === -2 && lastMsg.text !== undefined) {
            // Update existing message
            lastMsg.text = currentAiMessage;
        } else if (!lastMsg || lastMsg.type !== 'ai' || lastMsg.id !== -2) {
            // Create new message only once
            messages.value.push({
                id: -2,
                type: 'ai',
                text: currentAiMessage
            });
        }
    }

    // Event 459: ASR Ended (User finished speaking)
    if (data.question_id && !data.content && !data.results) {
        // Finalize user message
        if (currentUserMessage) {
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && lastMsg.type === 'user' && lastMsg.id === -1) {
                lastMsg.id = Date.now();
            }
            currentUserMessage = '';
        }
    }

    // Event 559: Chat Ended (AI finished replying)
    if (data.reply_id && !data.content) {
        // Finalize AI message
        if (currentAiMessage) {
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && lastMsg.type === 'ai' && lastMsg.id === -2) {
                lastMsg.id = Date.now();
            }

            // Calculate audio duration based on text length (rough estimate)
            // Chinese: ~3 characters per second, English: ~4 words per second
            const textLength = currentAiMessage.length;
            const estimatedDuration = (textLength / 3) * 1000; // milliseconds

            // Add buffer time (500ms) to ensure audio finishes
            const stopDelay = estimatedDuration + 500;

            console.log(`[Home] Scheduling lip sync stop in ${stopDelay}ms for text length ${textLength}`);

            // Clear any existing timer
            if (lipSyncStopTimer) {
                clearTimeout(lipSyncStopTimer);
            }

            // Schedule video stop
            lipSyncStopTimer = window.setTimeout(() => {
                if (digitalHumanRef.value) {
                    digitalHumanRef.value.stopExternalAudioSync();
                    isAvatarSpeaking.value = false;
                    console.log('[Home] Lip sync stopped');
                }
            }, stopDelay);

            currentAiMessage = '';
        }
    }
};

let phoneAudioContext: AudioContext | null = null;
let phoneMediaStream: MediaStream | null = null;
let phoneProcessor: ScriptProcessorNode | null = null;
let nextStartTime = 0;
let lastAudioSource: AudioBufferSourceNode | null = null;

const startPhoneCall = async () => {
    try {
        isPhoneActive.value = true;
        phoneStatus.value = '连接中...';
        
        // 1. Audio Context for Playback
        phoneAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
        nextStartTime = phoneAudioContext.currentTime;

        // 2. WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Add voice param for realtime phone mode
        let wsUrl = `${protocol}//${window.location.host}/ws/phone`;
        const params = new URLSearchParams();
        if (phoneVoice.value) {
            params.append('voice', phoneVoice.value);
        }
        if (sessionId.value) {
            params.append('conversation_id', sessionId.value);
        }
        if (params.toString()) {
            wsUrl += `?${params.toString()}`;
        }

        phoneWs = new WebSocket(wsUrl);
        phoneWs.binaryType = 'arraybuffer';
        
        phoneWs.onopen = () => {
            console.log('Phone WS Connected');
            phoneStatus.value = '通话中';
            startPhoneMicrophone();
        };
        
        phoneWs.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                // Play Audio
                playPcmChunk(event.data);
            } else {
                // Handle JSON events
                try {
                    const data = JSON.parse(event.data);
                    console.log('Phone Event:', data);
                    handlePhoneEvent(data);
                } catch(e) {
                    console.error('Failed to parse phone event:', e);
                }
            }
        };
        
        phoneWs.onclose = () => {
            console.log('Phone WS Closed');
            stopPhoneCall();
        };
        
        phoneWs.onerror = (e) => {
            console.error('Phone WS Error', e);
            showToast('通话连接失败');
            stopPhoneCall();
        };

    } catch (e) {
        console.error("Start phone call error:", e);
        showToast("无法启动通话");
        stopPhoneCall();
    }
};

const startPhoneMicrophone = async () => {
    try {
        phoneMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Use a separate context for recording if needed, or reuse. 
        // Note: Playback is 24k, Recording is 16k usually for ASR/Realtime.
        // Let's create a 16k context for recording to match Volc requirements if possible, 
        // or downsample.
        const recordContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
        const source = recordContext.createMediaStreamSource(phoneMediaStream);
        phoneProcessor = recordContext.createScriptProcessor(4096, 1, 1);
        
        source.connect(phoneProcessor);
        phoneProcessor.connect(recordContext.destination);
        
        phoneProcessor.onaudioprocess = (e) => {
            if (!phoneWs || phoneWs.readyState !== WebSocket.OPEN) return;
            
            const inputData = e.inputBuffer.getChannelData(0);
            
            // Convert Float32 to Int16
            const buffer = new ArrayBuffer(inputData.length * 2);
            const view = new DataView(buffer);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true); 
            }
            phoneWs.send(buffer);
        };
        
    } catch (e) {
        console.error("Phone Mic Error:", e);
        showToast("麦克风访问失败");
    }
};

const playPcmChunk = (arrayBuffer: ArrayBuffer) => {
    if (!phoneAudioContext) return;

    // Volcengine returns 32-bit Float PCM (not Int16)
    const float32 = new Float32Array(arrayBuffer);

    const buffer = phoneAudioContext.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const source = phoneAudioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(phoneAudioContext.destination);

    // Schedule playback
    if (nextStartTime < phoneAudioContext.currentTime) {
        nextStartTime = phoneAudioContext.currentTime;
    }
    source.start(nextStartTime);
    nextStartTime += buffer.duration;

    // Track the last audio source
    lastAudioSource = source;

    // Listen for audio end event
    source.onended = () => {
        // Only stop lip sync if this is the last audio chunk
        if (source === lastAudioSource) {
            console.log('[Home] Last audio chunk ended, stopping lip sync');
            if (digitalHumanRef.value) {
                digitalHumanRef.value.stopExternalAudioSync();
                isAvatarSpeaking.value = false;
            }
        }
    };
};

const stopPhoneCall = () => {
    isPhoneActive.value = false;
    phoneStatus.value = '点击通话';
    
    if (phoneWs) {
        phoneWs.close();
        phoneWs = null;
    }
    
    if (phoneMediaStream) {
        phoneMediaStream.getTracks().forEach(track => track.stop());
        phoneMediaStream = null;
    }
    
    if (phoneProcessor) {
        phoneProcessor.disconnect();
        phoneProcessor = null;
    }
    
    if (phoneAudioContext) {
        phoneAudioContext.close();
        phoneAudioContext = null;
    }
};

const togglePhoneCall = () => {
    if (isPhoneActive.value) {
        stopPhoneCall();
    } else {
        startPhoneCall();
    }
};

// Recording Logic
const isRecording = ref(false);
const recordingError = ref(false);
let mediaStream: MediaStream | null = null;
let audioContext: AudioContext | null = null;
let processor: ScriptProcessorNode | null = null;
let ws: WebSocket | null = null;

const startRecording = async () => {
  try {
    recordingError.value = false;
    if (inputMode.value === 'voice') {
        voiceInput.value = ''; 
    } else {
        if (!userInput.value) {
            userInput.value = '';
        } else {
            userInput.value += ' ';
        }
    }
    
    isRecording.value = true;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStream = stream;
    
    audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
    if (audioContext.state === 'suspended') {
        await audioContext.resume();
    }
    const source = audioContext.createMediaStreamSource(stream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    
    source.connect(processor);
    processor.connect(audioContext.destination);
    
    ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/asr`);
    
    ws.onopen = () => {
      console.log('ASR WebSocket Connected');
    };
    
    ws.onclose = (e) => {
        console.log('ASR WebSocket Closed', e.code, e.reason);
    };

    let lastAsrSendTime = 0;
    let pendingInterim = '';

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'asr_update') {
          if (data.finals && data.finals.length > 0) {
              if (inputMode.value !== 'voice' && pendingInterim && userInput.value.endsWith(pendingInterim)) {
                   userInput.value = userInput.value.slice(0, -pendingInterim.length);
              }

              data.finals.forEach((finalText: string) => {
                  if (inputMode.value === 'voice') {
                      userInput.value = finalText;
                      handleSend();
                      voiceInput.value = '';
                      lastAsrSendTime = Date.now();
                  } else {
                      userInput.value += finalText;
                  }
              });

              if (inputMode.value !== 'voice') {
                  pendingInterim = '';
              }
          }

          if (inputMode.value === 'voice') {
              voiceInput.value = data.interim || '';
          } else {
              if (pendingInterim && userInput.value.endsWith(pendingInterim)) {
                  userInput.value = userInput.value.slice(0, -pendingInterim.length);
              }

              if (data.interim) {
                  userInput.value += data.interim;
                  pendingInterim = data.interim;
              } else {
                  pendingInterim = '';
              }
          }

      } else if (data.text) {
        if (inputMode.value === 'voice') {
            voiceInput.value = data.text;
        } else {
            userInput.value = data.text;
        }
      }
    };
    
    ws.onerror = (e) => {
      console.error('ASR WebSocket Error', e);
      showToast('语音服务连接失败');
      if (inputMode.value === 'voice') {
          voiceInput.value = '连接失败，请重试';
      }
      recordingError.value = true;
      stopRecording();
    };

    let hasLoggedAudio = false;
    let lastVoiceTime = Date.now();
    const SILENCE_THRESHOLD = 0.05;
    const SILENCE_DURATION = 5000;

    processor.onaudioprocess = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      
      const inputData = e.inputBuffer.getChannelData(0);
      
      // VAD logic: Calculate max amplitude
      let maxAmp = 0;
      for (let i = 0; i < inputData.length; i++) {
        const abs = Math.abs(inputData[i]);
        if (abs > maxAmp) maxAmp = abs;
      }
      
      if (maxAmp > SILENCE_THRESHOLD) {
          lastVoiceTime = Date.now();
      } else {
          if (Date.now() - lastVoiceTime > SILENCE_DURATION) {
              stopRecording();
              return;
          }
      }

      if (!hasLoggedAudio) {
          hasLoggedAudio = true;
      }
      const buffer = new ArrayBuffer(inputData.length * 2);
      const view = new DataView(buffer);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true); 
      }
      ws.send(buffer);
    };
    
  } catch (e: any) {
    console.error('Microphone access failed', e);
    showToast(`无法访问麦克风: ${e.message || e}`);
    isRecording.value = false;
  }
};

const stopRecording = () => {
  isRecording.value = false;
  
  if (processor) {
    processor.disconnect();
    processor = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
    mediaStream = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  
  if (inputMode.value === 'voice' && voiceInput.value.trim() && !recordingError.value) {
      if (Date.now() - lastAsrSendTime > 3000) {
          userInput.value = voiceInput.value;
          handleSend();
      } else {
          console.log("Ignored VAD send due to recent ASR send");
      }
      voiceInput.value = '';
  }
  
  setTimeout(() => {
      recordingError.value = false;
  }, 500);
};

const toggleRecording = () => {
  if (isRecording.value) {
    stopRecording();
  } else {
    startRecording();
  }
};

const toggleVoiceRecording = () => {
  if (isRecording.value) {
    stopRecording();
  } else {
    startRecording(); 
  }
};

const cancelRecording = () => {
  recordingError.value = true; 
  stopRecording();
  showToast('录音已取消');
};

const handleSend = async (audioUrl?: string, duration?: number) => {
  const text = userInput.value.trim();
  if (!text) return;

  let lastUserMsg = null;
  for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].type === 'user') {
          lastUserMsg = messages.value[i];
          break;
      }
  }

  if (lastUserMsg) {
      const normalize = (str: string) => str.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, '');
      const normalizedText = normalize(text);
      const normalizedLast = normalize(lastUserMsg.text);

      if ((text === lastUserMsg.text || normalizedText === normalizedLast) && (Date.now() - lastUserMsg.id) < 2000) {
          console.log("Duplicate message ignored");
          userInput.value = '';
          if (inputMode.value === 'voice') voiceInput.value = '';
          return;
      }
  }
  
  messages.value.push({ id: Date.now(), type: 'user', text });
  userInput.value = '';
  
  isAiThinking.value = true;

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
          text,
          use_search: isWebSearchEnabled.value,
          session_id: sessionId.value
      })
    });
    
    const data = await response.json();
    const responseText = data.text;

    if (data.session_id) {
      sessionId.value = data.session_id;
    }
    
    if (digitalHumanRef.value && isVoiceReplyEnabled.value) {
      try {
        const spokenText = cleanTextForSpeech(responseText);
        await digitalHumanRef.value.speak(spokenText);
      } catch (e) {
      }
    }
    
    const newMessage = { 
        id: Date.now() + 1, 
        type: 'ai', 
        text: responseText,
        isPlaying: false 
    };
    
    if (isVoiceReplyEnabled.value) {
        newMessage.isPlaying = true;
    }

    messages.value.push(newMessage as Message);

  } catch (error) {
    messages.value.push({ id: Date.now() + 1, type: 'ai', text: "抱歉，我连接不上大脑了。" });
  } finally {
    isAiThinking.value = false;
  }
};

const clearChat = () => {
    sessionId.value = '';  // Clear session ID to start new conversation
    messages.value = [
      { id: Date.now(), type: 'ai', text: '您好！我是您的AI助教，有什么可以帮助您的吗？' }
    ];
    if (digitalHumanRef.value) {
        digitalHumanRef.value.stopSpeak();
    }
    showToast('已开启新对话');
};

const toggleAppsPanel = () => {
    isAppsPanelOpen.value = !isAppsPanelOpen.value;
};
</script>

<template>
  <div class="relative w-full h-screen bg-gradient-to-br from-pink-50 via-purple-50 to-blue-50 flex flex-col overflow-hidden font-sans">
      
      <!-- 1. Background Layer: Digital Human -->
      <div 
        class="absolute inset-0 z-0 flex pointer-events-none transition-all duration-500"
        :class="avatarFit === 'contain' ? 'items-start pt-20' : 'items-end'"
      >
         <div 
            class="w-full flex flex-col items-center pointer-events-auto transition-all duration-500"
            :class="avatarFit === 'contain' ? 'h-[60%] justify-start' : 'h-full justify-end'"
         >
            <DigitalHuman 
              ref="digitalHumanRef"
              :is-edit-mode="isEditMode"
              :avatar-fit="avatarFit"
              :avatar-scale="avatarScale"
              :tts-provider="ttsProvider"
              :volc-voice="volcVoice"
              @history-updated="loadHistory"
              @update:isSpeaking="(val) => isAvatarSpeaking = val"
              @avatar-loaded="(url) => currentAvatarUrl = url"
            />
         </div>
      </div>

      <!-- Mask Layer -->
      <div class="absolute inset-x-0 bottom-0 h-[65%] bg-gradient-to-t from-slate-50/90 via-blue-50/50 to-transparent pointer-events-none z-0"></div>

      <!-- 2. Foreground Layer -->
      <div class="absolute inset-0 z-10 flex flex-col pointer-events-none w-full h-full">
        
        <!-- Header (Cleaned) -->
        <header class="flex-none pt-14 pb-2 text-center pointer-events-auto flex justify-between px-6 items-center z-20">
             <button 
                @click="clearChat"
                class="p-2 rounded-full bg-white/30 backdrop-blur-md border border-white/40 shadow-sm active:scale-95 transition-all text-slate-600 hover:bg-white/50"
                title="新对话"
             >
                <PlusIcon class="w-5 h-5" />
             </button>

             <h1 class="text-sm font-semibold text-slate-700 tracking-wide bg-white/40 backdrop-blur-md px-4 py-1.5 rounded-full shadow-sm border border-white/40">
                数字人助手
             </h1>

             <!-- User Avatar Upload Button -->
             <button
                @click="userAvatarFileInput?.click()"
                class="w-9 h-9 rounded-full bg-white/30 backdrop-blur-md border border-white/40 shadow-sm active:scale-95 transition-all hover:bg-white/50 flex items-center justify-center overflow-hidden"
                title="上传头像"
             >
                <img v-if="userAvatarUrl" :src="userAvatarUrl" class="w-full h-full object-cover" alt="User Avatar" />
                <UserIcon v-else class="w-5 h-5 text-slate-600" />
             </button>
             <input
                ref="userAvatarFileInput"
                type="file"
                accept="image/*"
                @change="handleUserAvatarUpload"
                class="hidden"
             />
        </header>

        <!-- Chat Area -->
        <div class="flex-1 overflow-hidden pointer-events-none flex flex-col">
            <div class="h-[40%] w-full flex-none"></div>

            <div ref="chatContainerRef" class="flex-1 px-6 flex flex-col pointer-events-auto min-h-0 overflow-y-auto mask-fade-top scrollbar-hide pb-6">
                <div class="flex-1 flex flex-col justify-end space-y-4 w-full max-w-3xl mx-auto">
                  <transition-group name="list">
                    <div
                      v-for="msg in messages"
                      :key="msg.id"
                      class="flex gap-2.5 items-start"
                      :class="msg.type === 'user' ? 'justify-end' : 'justify-start'"
                    >
                      <div v-if="msg.type === 'ai'" class="w-8 h-8 rounded-full bg-white border border-slate-200 shadow-sm flex items-center justify-center overflow-hidden shrink-0 mt-0.5">
                        <img :src="aiAvatarUrl" class="w-full h-full object-cover" alt="AI" />
                      </div>

                      <div
                        class="relative px-4 py-2.5 text-[14px] leading-[1.5] max-w-[75%] break-words transition-all duration-300 group/bubble"
                        :class="[
                          msg.type === 'user'
                            ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white rounded-2xl rounded-tr-md shadow-lg shadow-blue-500/10'
                            : 'bg-white/70 backdrop-blur-md text-slate-800 rounded-2xl rounded-tl-md border border-white/50 shadow-sm'
                        ]"
                      >

                        <template v-if="msg.contentType === 'audio'">
                           <div class="flex items-center gap-2 cursor-pointer" @click="playAudio(msg.audioUrl)">
                              <SpeakerWaveIcon class="w-5 h-5" />
                              <span>{{ Math.round(msg.audioDuration || 0) }}''</span>
                           </div>
                           <div v-if="msg.text" class="text-[13px] mt-1 pt-1 border-t border-white/20 opacity-90">
                              {{ msg.text }}
                           </div>
                        </template>
                        <template v-else>
                           <div 
                             v-if="msg.type === 'ai'" 
                             class="prose-custom" 
                             v-html="renderMarkdown(msg.text)"
                           ></div>
                           <div v-else>
                             {{ msg.text }}
                           </div>

                           <div v-if="msg.type === 'ai'" class="mt-1 flex justify-end -mb-2 -mr-2">
                              <button 
                                @click="toggleSpeech(msg)"
                                class="flex items-center justify-center w-8 h-8 rounded-full transition-all active:scale-95 opacity-60 hover:opacity-100"
                                :class="{'text-red-500': msg.isPlaying, 'text-slate-500 hover:text-blue-500': !msg.isPlaying}"
                              >
                                <template v-if="msg.isPlaying">
                                    <StopIcon class="w-5 h-5 drop-shadow-sm" />
                                </template>
                                <template v-else>
                                    <SpeakerWaveIcon class="w-4 h-4" />
                                </template>
                              </button>
                           </div>
                        </template>
                      </div>

                      <div v-if="msg.type === 'user'" class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 border border-white/50 shadow-sm flex items-center justify-center overflow-hidden shrink-0 mt-0.5">
                        <img v-if="userAvatarUrl" :src="userAvatarUrl" class="w-full h-full object-cover" alt="User" />
                        <UserIcon v-else class="w-4 h-4 text-white" />
                      </div>
                    </div>

                    <div v-if="isAiThinking" key="thinking" class="flex gap-2.5 items-start justify-start">
                       <div class="w-8 h-8 rounded-full bg-white border border-slate-200 shadow-sm flex items-center justify-center overflow-hidden shrink-0 mt-0.5">
                          <img :src="aiAvatarUrl" class="w-full h-full object-cover" alt="AI" />
                       </div>
                       <div class="bg-white/80 backdrop-blur-sm text-slate-500 rounded-2xl rounded-tl-md border border-white/50 px-4 py-2.5 shadow-sm flex items-center gap-2">
                          <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                          <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                          <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
                       </div>
                    </div>

                  </transition-group>
                </div>
            </div>
        </div>

        <!-- Voice Recording Overlay -->
        <div 
           v-if="isRecording && inputMode === 'voice'"
           class="absolute inset-0 z-50 flex flex-col items-center bg-slate-900/40 backdrop-blur-md transition-all duration-500 pointer-events-auto py-12 px-6"
        >
           <div class="flex-none h-[25%] relative flex items-center justify-center w-full">
              <div class="absolute w-40 h-40 bg-blue-300/30 rounded-full animate-ping opacity-20 duration-[2000ms]"></div>
              <div class="absolute w-32 h-32 bg-indigo-300/40 rounded-full animate-ping opacity-40 duration-[1500ms] delay-300"></div>
              <div class="absolute w-24 h-24 bg-purple-300/50 rounded-full animate-pulse"></div>
              
              <div class="w-20 h-20 bg-gradient-to-br from-blue-400 to-indigo-400 rounded-full flex items-center justify-center shadow-lg shadow-indigo-500/30 relative z-10 ring-4 ring-white/40">
                 <MicrophoneIcon class="w-9 h-9 text-white drop-shadow-sm" />
              </div>
           </div>

           <div class="flex-1 w-full min-h-0 flex flex-col justify-center items-center my-6">
              <div class="w-full max-h-full bg-white/90 backdrop-blur-xl rounded-[32px] p-8 shadow-xl shadow-blue-900/10 text-center flex items-center justify-center border border-white/60 overflow-y-auto scrollbar-hide">
                  <p class="text-lg font-medium text-slate-700 leading-relaxed tracking-wide break-words w-full">
                     {{ voiceInput || '正在聆听...' }}
                  </p>
              </div>
           </div>

           <div class="flex-none w-full flex flex-col items-center gap-6">
              <button
                  @click="toggleVoiceRecording"
                  class="w-48 py-3.5 rounded-full bg-gradient-to-r from-blue-400 to-indigo-400 text-white font-semibold text-base shadow-lg shadow-blue-400/30 active:scale-95 transition-all flex items-center justify-center gap-2 border border-white/20 hover:shadow-blue-400/50"
              >
                  <PaperAirplaneIcon class="w-5 h-5 rotate-[-15deg] mb-0.5" />
                  <span>点击发送</span>
              </button>

              <button 
                  @click="cancelRecording" 
                  class="px-4 py-2 rounded-full text-white/80 hover:text-white hover:bg-white/10 text-sm transition-all flex items-center gap-1.5"
              >
                  <XMarkIcon class="w-4 h-4" />
                  <span>取消</span>
              </button>
           </div>
        </div>

        <!-- Bottom Panel -->
        <div class="flex-none pointer-events-auto relative z-30">
          
          <!-- Apps Grid Panel -->
          <div 
             class="absolute bottom-full left-0 right-0 mx-4 mb-2 bg-white/80 backdrop-blur-2xl rounded-[24px] p-4 shadow-xl border border-white/60 transition-all duration-300 ease-out origin-bottom z-0"
             :class="isAppsPanelOpen ? 'opacity-100 scale-100 translate-y-0 pointer-events-auto' : 'opacity-0 scale-95 translate-y-[20px] pointer-events-none'"
          >
            <div class="grid grid-cols-4 gap-y-4 gap-x-2">
              <div 
                v-for="app in apps" 
                :key="app.name" 
                class="flex flex-col items-center gap-2 cursor-pointer group"
                @click="handleAppClick(app)"
              >
                <div 
                  :class="[app.color, 'w-12 h-12 rounded-[16px] flex items-center justify-center text-white shadow-lg shadow-blue-100/50 transition-transform duration-200 active:scale-95 bg-gradient-to-br border border-white/20']"
                >
                  <component :is="app.icon" class="w-6 h-6 drop-shadow-sm" />
                </div>
                <span class="text-[10px] text-slate-500 font-medium tracking-tight">{{ app.name }}</span>
              </div>
            </div>
          </div>

          <!-- Bottom Input Bar -->
          <div class="px-4 pb-6 pt-2 w-full relative z-[60]">
             <div class="bg-white/70 backdrop-blur-2xl p-2 rounded-[18px] flex items-end gap-2 border border-white/50 shadow-2xl shadow-blue-900/5 ring-1 ring-white/40 min-h-[56px]">
                
                <button 
                  class="w-10 h-10 mb-0.5 rounded-[16px] flex items-center justify-center bg-white/50 text-slate-600 hover:bg-white hover:text-blue-600 transition-all active:scale-95 flex-none shadow-sm border border-white/40"
                  @click="isPhoneMode = !isPhoneMode; if(!isPhoneMode) stopPhoneCall();"
                  aria-label="Toggle Phone Mode"
                  :class="{'text-green-500 bg-green-50 border-green-200': isPhoneMode}"
                >
                  <PhoneIcon class="w-5 h-5" />
                </button>

                <div class="flex-1 relative min-w-0 flex items-center h-full">
                  <!-- Phone Mode UI -->
                  <div v-if="isPhoneMode" class="w-full flex items-center justify-center gap-4">
                      <button
                        v-if="!isPhoneActive"
                        @click="showConversationList = true; loadConversations()"
                        class="h-[44px] px-6 rounded-full font-semibold text-[14px] transition-all flex items-center justify-center gap-2 shadow-md active:scale-95 border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100"
                      >
                         <ChatBubbleLeftRightIcon class="w-5 h-5" />
                         <span>选择对话</span>
                      </button>

                      <button
                        @click="togglePhoneCall"
                        class="h-[44px] px-8 rounded-full font-semibold text-[14px] transition-all flex items-center justify-center gap-2 shadow-md active:scale-95 border border-white/20"
                        :class="[
                          isPhoneActive
                            ? 'bg-red-500 text-white shadow-red-500/30 hover:bg-red-600'
                            : 'bg-green-500 text-white shadow-green-500/30 hover:bg-green-600'
                        ]"
                      >
                         <PhoneIcon class="w-5 h-5" :class="{'rotate-[135deg]': isPhoneActive}" />
                         <span>{{ isPhoneActive ? '挂断' : phoneStatus }}</span>
                      </button>

                      <div v-if="isPhoneActive" class="text-slate-500 text-sm font-medium animate-pulse">
                         {{ phoneStatus }}
                      </div>
                  </div>

                  <!-- Normal Chat UI -->
                  <div 
                    v-else
                    v-show="inputMode === 'text'"
                    class="w-full bg-white/60 rounded-[18px] border border-white/40 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-400/20 focus-within:border-blue-300/50 transition-all flex items-center relative"
                  >
                    <textarea
                      ref="textareaRef"
                      v-model="userInput"
                      @keydown.enter.prevent="() => handleSend()"
                      :disabled="isAiThinking"
                      placeholder="发消息..."
                      class="w-full bg-transparent border-none py-2.5 px-4 pr-10 text-[14px] focus:ring-0 transition-all outline-none text-slate-800 placeholder-slate-500 caret-blue-600 resize-none max-h-[120px] scrollbar-hide leading-relaxed disabled:opacity-50"
                      rows="1"
                      aria-label="Message Input"
                      style="min-height: 44px;"
                      @input="(e) => {
                        const target = e.target as HTMLTextAreaElement;
                        target.style.height = 'auto';
                        target.style.height = target.scrollHeight + 'px';
                      }"
                    ></textarea>
                    
                    <button 
                      class="absolute right-1.5 bottom-[5px] p-1.5 text-slate-500 hover:text-blue-600 active:scale-95 transition-all rounded-[12px] hover:bg-blue-50"
                      @click="toggleRecording"
                      :class="{'text-red-500 bg-red-50 hover:text-red-600 animate-pulse': isRecording && inputMode === 'text'}"
                      aria-label="Voice Input"
                    >
                      <StopIcon v-if="isRecording && inputMode === 'text'" class="w-5 h-5" />
                      <MicrophoneIcon v-else class="w-5 h-5" />
                    </button>
                  </div>

                  <button
                    v-if="!isPhoneMode && inputMode === 'voice'"
                    class="w-full h-[44px] rounded-[18px] font-semibold text-[14px] transition-all select-none touch-none flex items-center justify-center gap-2 shadow-sm border border-transparent active:scale-95"
                    :class="[
                      isAiThinking ? 'opacity-50 cursor-not-allowed bg-slate-100 text-slate-400' :
                      isRecording ? 'bg-green-500 text-white shadow-green-200 shadow-md animate-pulse' : 'bg-white/80 text-slate-700 border-white/40 hover:bg-white'
                    ]"
                    :disabled="isAiThinking"
                    @click="toggleVoiceRecording"
                  >
                    <span>{{ isAiThinking ? '思考中...' : (isRecording ? '点击 发送' : '点击 说话') }}</span>
                  </button>
                </div>

                <button 
                  v-if="!isPhoneMode"
                  class="w-10 h-10 mb-0.5 rounded-[16px] flex items-center justify-center bg-white/50 text-slate-600 hover:bg-white hover:text-blue-600 transition-all active:scale-95 flex-none shadow-sm border border-white/40"
                  @click="toggleAppsPanel"
                  :class="{'text-blue-600 bg-blue-50 border-blue-200': isAppsPanelOpen}"
                  aria-label="Toggle Apps Panel"
                >
                  <div v-if="!isAppsPanelOpen" class="w-5 h-5 grid grid-cols-2 gap-[3px]">
                      <div class="bg-current rounded-[1.5px]"></div><div class="bg-current rounded-[1.5px]"></div>
                      <div class="bg-current rounded-[1.5px]"></div><div class="bg-current rounded-[1.5px]"></div>
                  </div>
                  <XMarkIcon v-else class="w-6 h-6" />
                </button>

                <button 
                  v-if="!isPhoneMode && inputMode === 'text'"
                  class="w-10 h-10 mb-0.5 rounded-[16px] flex items-center justify-center transition-all active:scale-90 flex-none shadow-md"
                  @click="() => handleSend()"
                  :disabled="!userInput.trim() || isAiThinking"
                  :class="[
                    userInput.trim() && !isAiThinking
                      ? 'bg-gradient-to-tr from-blue-500 to-indigo-600 text-white shadow-blue-500/30 hover:shadow-blue-500/40' 
                      : 'bg-slate-200 text-slate-400 shadow-none cursor-not-allowed opacity-50'
                  ]"
                  aria-label="Send Message"
                >
                  <PhoneIcon class="w-5 h-5 rotate-90" />
                </button>
             </div>
          </div>
        </div>
      </div>
  </div>

  <!-- Conversation List Modal -->
  <div v-if="showConversationList" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4" @click.self="showConversationList = false">
      <div class="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[70vh] overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between p-4 border-b border-slate-200">
              <h2 class="text-lg font-bold text-slate-800">选择对话</h2>
              <button @click="showConversationList = false" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">
                  <XMarkIcon class="w-5 h-5 text-slate-500" />
              </button>
          </div>

          <!-- Conversation List -->
          <div class="flex-1 overflow-y-auto p-4">
              <div v-if="conversations.length === 0" class="text-center py-12 text-slate-400">
                  暂无对话记录
              </div>
              <div v-else class="space-y-2">
                  <div
                      v-for="conv in conversations"
                      :key="conv.id"
                      class="p-3 rounded-lg cursor-pointer transition-all hover:bg-slate-50 border border-transparent hover:border-blue-200"
                      :class="sessionId === conv.id ? 'bg-blue-50 border-blue-300' : ''"
                      @click="selectConversation(conv)"
                  >
                      <div class="flex items-start justify-between gap-2">
                          <div class="flex-1 min-w-0">
                              <div class="text-sm font-medium text-slate-800 truncate">
                                  {{ conv.title || '新对话' }}
                              </div>
                              <div class="text-xs text-slate-500 mt-1">
                                  {{ new Date(conv.created_at * 1000).toLocaleDateString() }}
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
          </div>

          <!-- Footer -->
          <div class="p-4 border-t border-slate-200">
              <button
                  @click="createNewConversation"
                  class="w-full py-2.5 rounded-xl bg-blue-600 text-white font-medium shadow-md hover:bg-blue-700 active:scale-95 transition-all flex items-center justify-center gap-2"
              >
                  <PlusIcon class="w-5 h-5" />
                  <span>新建对话</span>
              </button>
          </div>
      </div>
  </div>
</template>

<style>
/* Global Utilities */
.scrollbar-hide::-webkit-scrollbar {
    display: none;
}
.scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;
}

.mask-fade-top {
  mask-image: linear-gradient(to bottom, transparent, black 20px);
  -webkit-mask-image: linear-gradient(to bottom, transparent, black 20px);
}

/* Transitions */
.list-enter-active,
.list-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

/* Markdown Custom Styles */
.prose-custom {
  font-size: 13px;
  line-height: 1.5;
}
.prose-custom p {
  margin-bottom: 0.3em;
}
.prose-custom p:last-child {
  margin-bottom: 0;
}
.prose-custom ul {
  list-style-type: disc;
  padding-left: 1.2em;
  margin-bottom: 0.3em;
}
.prose-custom ol {
  list-style-type: decimal;
  padding-left: 1.2em;
  margin-bottom: 0.3em;
}
.prose-custom li {
  margin-bottom: 0.1em;
}
.prose-custom strong {
  font-weight: 600;
  color: #1e293b;
}
.prose-custom a {
  color: #3b82f6;
  text-decoration: underline;
}
.prose-custom h1, .prose-custom h2, .prose-custom h3 {
  font-weight: 700;
  margin-top: 0.8em;
  margin-bottom: 0.4em;
  color: #0f172a;
}
.prose-custom code {
  background-color: rgba(255, 255, 255, 0.6);
  padding: 0.1em 0.3em;
  border-radius: 0.3em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9em;
  color: #be185d;
}
.prose-custom pre {
  background-color: #1e293b;
  color: #f8fafc;
  padding: 0.8em;
  border-radius: 0.8em;
  overflow-x: auto;
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}
.prose-custom pre code {
  background-color: transparent;
  padding: 0;
  color: inherit;
  font-size: 0.85em;
  white-space: pre;
}
.prose-custom blockquote {
  border-left: 4px solid #cbd5e1;
  padding-left: 1em;
  color: #64748b;
  margin-bottom: 0.5em;
  font-style: italic;
}
</style>
