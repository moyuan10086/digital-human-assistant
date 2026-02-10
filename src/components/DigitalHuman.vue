<script setup lang="ts">
import { ref, watch } from 'vue';
import { removeBackground } from '@imgly/background-removal';
import { showToast, showLoadingToast, closeToast } from 'vant';
import 'vant/es/toast/style';

// Props Interface
interface Props {
  isEditMode?: boolean;
  triggerSpeak?: string;
  avatarFit?: 'cover' | 'contain'; // Control display mode
  avatarScale?: number; // New: Scale factor
  ttsProvider?: 'microsoft' | 'volcengine'; // TTS Provider
  volcVoice?: string; // Selected Volcengine Voice
}

const props = withDefaults(defineProps<Props>(), {
  isEditMode: false,
  triggerSpeak: '',
  avatarFit: 'cover',
  avatarScale: 1.0,
  ttsProvider: 'microsoft',
  volcVoice: 'zh_female_meilinvyou_moon_bigtts'
});

// State
const imageSrc = ref<string | null>(null);
const videoSrc = ref<string | null>(null);
const videoLoopSrc = ref<string | null>(null); // New: Stores the looping talking video
const isSpeaking = ref(false);
const isProcessing = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const videoRef = ref<HTMLVideoElement | null>(null);
const audioRef = ref<HTMLAudioElement | null>(null); // New: Audio player

// Methods
const triggerFileInput = (meta?: any) => {
  if (fileInput.value) {
    (fileInput.value as any)._meta = meta;
    fileInput.value.click();
  }
};

const onFileChange = async (e: Event) => {
  const target = e.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  // Stop any ongoing speech/video
  stopSpeak();

  isProcessing.value = true;
  const loadingToast = showLoadingToast({
    message: '智能抠图中...',
    forbidClick: true,
    duration: 0
  });

  try {
    // 1. Remove background
    const blob = await removeBackground(file, {
      progress: (key: string, current: number, total: number) => {
        // Optional: Update progress UI
      }
    });
    const url = URL.createObjectURL(blob);
    imageSrc.value = url;
    videoSrc.value = null; // Reset video
    videoLoopSrc.value = null;

    // 2. Pre-generate Looping Video (Call /animate)
    const formData = new FormData();
    formData.append('image', blob, 'avatar.png'); // Send processed image
    
    // Get meta if available
    const meta = (fileInput.value as any)?._meta || {};
    if (meta.fit) formData.append('avatar_fit', meta.fit);
    if (meta.scale) formData.append('avatar_scale', meta.scale.toString());
    
    const animateResponse = await fetch('http://localhost:8004/animate', {
      method: 'POST',
      body: formData
    });

    if (animateResponse.ok) {
      const videoBlob = await animateResponse.blob();
      videoLoopSrc.value = URL.createObjectURL(videoBlob);
      console.log("Loop video ready:", videoLoopSrc.value);
      
      // Save to History
      const avatarUrl = animateResponse.headers.get("X-Avatar-Url");
      if (avatarUrl) {
          emit('history-updated');
          emit('avatar-loaded', avatarUrl);
      }
    } else {
      console.warn("Failed to generate loop video, fallback to static image.");
    }
    
    closeToast();
    showToast({
      type: 'success',
      message: '形象处理完成',
      className: 'custom-toast' // We will style this
    });

  } catch (error) {
    console.error('Processing failed:', error);
    closeToast();
    showToast({
      type: 'fail',
      message: '图片处理失败',
    });
    
    // Fallback: use original image
    const reader = new FileReader();
    reader.onload = (e) => {
      imageSrc.value = e.target?.result as string;
    };
    reader.readAsDataURL(file);
  } finally {
    isProcessing.value = false;
    target.value = '';
  }
};

const emit = defineEmits(['history-updated', 'update:isSpeaking', 'avatar-loaded']);

const loadAvatarFromUrl = (url: string) => {
    // Stop any ongoing speech/video before switching
    stopSpeak();

    videoLoopSrc.value = url;
    imageSrc.value = url;

    emit('avatar-loaded', url);

    // Reset other states
    videoSrc.value = null;
    isSpeaking.value = false;
    emit('update:isSpeaking', false);

    console.log('[DigitalHuman] Avatar loaded:', url);
};

const currentText = ref<string>(''); // New: Track current spoken text

// Watch for voice changes to reset current text, forcing re-generation
watch(() => props.volcVoice, () => {
    currentText.value = ''; // Clear cache key to force new TTS request
    // Optional: stop current speech?
    // stopSpeak(); // Maybe better to let user stop manually or let it finish?
    // But if they changed voice, they probably want next speech to use it.
    // Clearing currentText ensures 'Resume' logic doesn't kick in with old audio.
});

watch(() => props.ttsProvider, () => {
    currentText.value = '';
});

const stopSpeak = () => {
    if (audioRef.value) {
        audioRef.value.pause();
        // Do NOT reset currentTime to 0 to support Resume
        // audioRef.value.currentTime = 0; 
    }
    if (videoRef.value) {
        videoRef.value.pause();
        videoRef.value.currentTime = 0; // Video loop should reset? Or pause?
        // Usually reset video loop to first frame (closed mouth) looks better for pause
        // But if we want perfect sync resume, we might want to pause video too?
        // Let's reset video to be safe/clean for now, or just pause.
        // If we reset video, it might jump. Let's just pause.
        // But loop video usually has talking mouth everywhere.
        // For now, let's keep video reset to 0 to ensure mouth closes (if frame 0 is closed)
        videoRef.value.currentTime = 0;
    }
    isSpeaking.value = false;
    emit('update:isSpeaking', false);
};

const speak = (text: string): Promise<void> => {
  return new Promise(async (resolve, reject) => {
    if (!text) {
        resolve();
        return;
    }
    
    // Resume Logic: If text matches and we have audio source, just play
    if (text === currentText.value && audioRef.value && audioRef.value.src) {
        if (audioRef.value.paused) {
            // If ended, restart from 0
            if (audioRef.value.ended) {
                audioRef.value.currentTime = 0;
            }
            
            // Resume
            isSpeaking.value = true;
            emit('update:isSpeaking', true);
            if (videoRef.value) {
                videoRef.value.play().catch(e => console.error("Video resume failed:", e));
            }
            audioRef.value.play().catch(e => console.error("Audio resume failed:", e));
            resolve();
            return;
        } else {
            // Already playing
            resolve();
            return;
        }
    }
  
    // New Speak Logic
    isProcessing.value = true;
    currentText.value = text; // Update current text
    
    try {
        const formData = new FormData();
        formData.append('text', text);
        formData.append('tts_provider', props.ttsProvider); // Pass selected provider
        // Pass specific voice if provider is volcengine
        if (props.ttsProvider === 'volcengine' && props.volcVoice) {
            formData.append('voice', props.volcVoice);
        }
        
        // Call Backend API - TTS Only
    const apiResponse = await fetch('http://localhost:8004/tts', {
      method: 'POST',
      body: formData
    });

        if (!apiResponse.ok) {
            throw new Error(`Backend error: ${apiResponse.statusText}`);
        }

        const audioBlob = await apiResponse.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        
        // Play Audio & Video Loop
        if (audioRef.value) {
            audioRef.value.src = audioUrl;
            
            // Wait for audio to be ready to play
            audioRef.value.oncanplaythrough = () => {
                // Start video loop immediately (visual feedback)
                isSpeaking.value = true;
                emit('update:isSpeaking', true);
                if (videoRef.value) {
                    videoRef.value.play().catch(e => console.error("Video play failed:", e));
                }

                // Start audio
                audioRef.value!.play().catch(e => console.error("Audio play failed:", e));
                resolve(); // Audio is ready and playing!
            };
            
            // Sync stop
            audioRef.value.onended = () => {
                isSpeaking.value = false;
                emit('update:isSpeaking', false);
                if (videoRef.value) {
                    videoRef.value.pause();
                    videoRef.value.currentTime = 0; // Reset to start frame (cover)
                }
            };
            
            audioRef.value.onerror = (e) => {
                isSpeaking.value = false;
                emit('update:isSpeaking', false);
                if (videoRef.value) videoRef.value.pause();
                reject(e);
            };
        } else {
            resolve();
        }

    } catch (error) {
        console.error("Generate failed:", error);
        isSpeaking.value = false;
        emit('update:isSpeaking', false);
        showToast({
            type: 'fail',
            message: '生成失败，请检查服务',
        });
        reject(error);
    } finally {
        isProcessing.value = false;
    }
  });
};

// New: Start external audio monitoring for lip sync
const startExternalAudioSync = () => {
    console.log('[DigitalHuman] startExternalAudioSync called');
    console.log('[DigitalHuman] videoRef:', videoRef.value);
    console.log('[DigitalHuman] videoLoopSrc:', videoLoopSrc.value);

    if (videoRef.value && videoLoopSrc.value) {
        isSpeaking.value = true;
        emit('update:isSpeaking', true);
        videoRef.value.play().catch(e => console.error("Video play failed:", e));
        console.log('[DigitalHuman] Video play started');
    } else {
        console.warn('[DigitalHuman] Cannot start sync - missing video or videoLoopSrc');
    }
};

// New: Stop external audio monitoring
const stopExternalAudioSync = () => {
    if (videoRef.value) {
        videoRef.value.pause();
        videoRef.value.currentTime = 0;
    }
    isSpeaking.value = false;
    emit('update:isSpeaking', false);
};

watch(() => props.triggerSpeak, (newVal) => {
  if (newVal) {
    speak(newVal);
  }
});

defineExpose({
  hasImage: () => !!imageSrc.value,
  speak,
  stopSpeak,
  triggerFileInput,
  loadAvatarFromUrl,
  startExternalAudioSync,
  stopExternalAudioSync
});
</script>

<template>
  <div class="relative w-full h-full flex flex-col items-center justify-center bg-gray-50/50">
    
    <!-- Loading Overlay (Vant style is handled by Toast, but we keep a subtle local spinner for video generation) -->
    <div v-if="isProcessing && isSpeaking" class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-white/60 backdrop-blur-sm transition-all duration-300">
      <div class="flex flex-col items-center gap-4">
        <div class="loading-spinner"></div>
        <span class="text-sm font-medium text-slate-600 tracking-wide">AI 正在生成视频...</span>
      </div>
    </div>

    <!-- Avatar Container (Video Only) -->
    <div 
      id="avatar-container"
      class="relative w-full h-full flex transition-all duration-500 overflow-hidden"
      :class="[
        {'opacity-0': !imageSrc && !isProcessing, 'opacity-100': imageSrc || isProcessing},
        avatarFit === 'cover' ? 'items-end justify-center' : 'items-start justify-center'
      ]"
    >
      <!-- Single Video Element for Both Static and Playing States -->
      <video 
        v-if="videoLoopSrc"
        ref="videoRef"
        :src="videoLoopSrc"
        class="w-full transition-all duration-500 origin-bottom"
        :class="avatarFit === 'cover' ? 'h-full object-cover object-top' : 'h-full object-contain object-top'"
        :style="{ transform: `scale(${avatarScale})` }"
        playsinline
        loop
        muted
        :autoplay="false"
      ></video>
      
      <!-- Fallback Image (Only if video generation failed) -->
      <img 
        v-else-if="imageSrc"
        :src="imageSrc" 
        class="w-full transition-all duration-500 origin-bottom" 
        :class="avatarFit === 'cover' ? 'h-full object-cover object-top' : 'h-full object-contain object-top'"
        :style="{ transform: `scale(${avatarScale})` }"
        alt="Digital Human"
      />
    </div>

    <!-- Hidden Audio Player -->
    <audio ref="audioRef" class="hidden"></audio>

    <!-- Empty State / Logo (When no image) -->
    <div v-if="!imageSrc" class="absolute inset-0 flex flex-col items-center justify-center text-slate-400 -mt-16 pointer-events-none">
      <!-- Minimalist Logo -->
      <div class="relative w-32 h-32 mb-6 group">
        <!-- Glow Effect -->
        <div class="absolute inset-0 bg-blue-500/20 rounded-[32px] blur-xl group-hover:bg-blue-500/30 transition-colors duration-500"></div>
        <div class="relative w-full h-full bg-gradient-to-tr from-white to-blue-50 rounded-[32px] shadow-lg border border-white/80 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-14 w-14 text-blue-500 drop-shadow-sm" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
             <path stroke-linecap="round" stroke-linejoin="round" d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4" />
          </svg>
        </div>
      </div>
      <h2 class="text-xl font-semibold text-slate-700 mb-2 tracking-tight">数字人助手</h2>
      <p class="text-sm text-slate-400 font-normal">请上传形象以开始对话</p>
    </div>

    <!-- Hidden Input -->
    <input 
      type="file" 
      accept="image/*" 
      @change="onFileChange" 
      ref="fileInput"
      class="hidden"
      id="hidden-file-input"
      aria-label="Upload Avatar"
    />
  </div>
</template>

<style scoped>
/* Custom Minimal Spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
