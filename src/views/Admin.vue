<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import { 
  CameraIcon,
  XMarkIcon,
  ArrowLeftOnRectangleIcon
} from '@heroicons/vue/24/solid';
import { showToast, Cell as VanCell, Switch as VanSwitch, Slider as VanSlider, Stepper as VanStepper } from 'vant';
import 'vant/es/toast/style';
import 'vant/es/cell/style';
import 'vant/es/switch/style';
import 'vant/es/slider/style';
import 'vant/es/stepper/style';

// Types
interface AvatarItem {
  url: string;
  meta?: {
    fit?: 'cover' | 'contain';
    scale?: number;
    ttsProvider?: 'microsoft' | 'volcengine';
    volcVoice?: string;
    phoneVoice?: string;
    systemPrompt?: string;
    speakingStyle?: string;
    isWebSearchEnabled?: boolean;
    isVoiceReplyEnabled?: boolean;
  };
}

// State
const avatarHistory = ref<AvatarItem[]>([]);
const currentAvatarUrl = ref<string>(''); // Currently selected/active avatar (if any)

// Settings State
const isWebSearchEnabled = ref(true);
const isVoiceReplyEnabled = ref(true);
const avatarFit = ref<'cover' | 'contain'>('cover');
const avatarScale = ref<number>(1.0);
const ttsProvider = ref<'microsoft' | 'volcengine'>('microsoft');
const volcVoice = ref('zh_female_meilinvyou_moon_bigtts');
const phoneVoice = ref('zh_female_vv_jupiter_bigtts');
const systemPrompt = ref('你使用活泼灵动的女声，性格开朗，热爱生活。');
const speakingStyle = ref('你的说话风格简洁明了，语速适中，语调自然。');

const volcVoices = [
    { name: '魅力女友', id: 'zh_female_meilinvyou_moon_bigtts' },
    { name: '少年梓辛', id: 'zh_male_shaonianzixin_moon_bigtts' },
    { name: '深夜播客', id: 'zh_male_shenyeboke_moon_bigtts' },
    { name: '柔美女友', id: 'zh_female_sajiaonvyou_moon_bigtts' },
    { name: '撒娇学妹', id: 'zh_female_yuanqinvyou_moon_bigtts' },
    { name: '浩宇小哥', id: 'zh_male_haoyuxiaoge_moon_bigtts' },
    { name: '邻家女孩', id: 'zh_female_linjianvhai_moon_bigtts' },
    { name: '高冷御姐', id: 'zh_female_gaolengyujie_moon_bigtts' },
    { name: '渊博小叔', id: 'zh_male_yuanboxiaoshu_moon_bigtts' },
    { name: '阳光青年', id: 'zh_male_yangguangqingnian_moon_bigtts' }
];

const phoneVoices = [
    { name: 'VV(女声-活泼)', id: 'zh_female_vv_jupiter_bigtts' },
    { name: '小荷(女声-甜美)', id: 'zh_female_xiaohe_jupiter_bigtts' },
    { name: '云舟(男声-沉稳)', id: 'zh_male_yunzhou_jupiter_bigtts' },
    { name: '小天(男声-磁性)', id: 'zh_male_xiaotian_jupiter_bigtts' }
];

// Chat History - Conversation Management
const conversations = ref<any[]>([]);
const selectedConversation = ref<any>(null);
const conversationMessages = ref<any[]>([]);
const showChatHistory = ref(false);
const aiAvatarUrl = ref<string>('');
const aiAvatarFileInput = ref<HTMLInputElement | null>(null);

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

const loadConversationMessages = async (convId: string) => {
    try {
        const response = await fetch(`/api/conversations/${convId}/messages`);
        if (response.ok) {
            conversationMessages.value = await response.json();
        }
    } catch (e) {
        console.error("Failed to load messages", e);
    }
};

const selectConversation = async (conv: any) => {
    selectedConversation.value = conv;
    await loadConversationMessages(conv.id);
};

const deleteConversation = async (convId: string) => {
    if (!confirm('确定要删除这个对话吗？')) return;

    try {
        const response = await fetch(`/api/conversations/${convId}`, { method: 'DELETE' });
        if (response.ok) {
            await loadConversations();
            if (selectedConversation.value?.id === convId) {
                selectedConversation.value = null;
                conversationMessages.value = [];
            }
            showToast('对话已删除');
        }
    } catch (e) {
        console.error("Failed to delete conversation", e);
        showToast('删除失败');
    }
};

// Load Config
const loadConfig = async () => {
    try {
        const response = await fetch('/config');
        if (response.ok) {
            const config = await response.json();
            if (config.aiAvatarUrl) {
                aiAvatarUrl.value = config.aiAvatarUrl;
            }
        }
    } catch (e) {
        console.error("Failed to load config", e);
    }
};

// Load History
const loadHistory = async () => {
    try {
        const response = await fetch(`/history?t=${Date.now()}`);
        if (response.ok) {
            avatarHistory.value = await response.json();
            if (avatarHistory.value.length > 0) {
                selectAvatar(avatarHistory.value[0]);
            }
        }
    } catch (e) {
    }
};

const selectAvatar = (item: AvatarItem | string) => {
    const url = typeof item === 'string' ? item : item.url;
    const meta = typeof item === 'string' ? {} : (item.meta || {});

    currentAvatarUrl.value = url;

    isInternalUpdate.value = true;

    if (meta.fit) avatarFit.value = meta.fit;
    if (meta.scale !== undefined) avatarScale.value = meta.scale;

    if (meta.ttsProvider) ttsProvider.value = meta.ttsProvider;
    if (meta.volcVoice) volcVoice.value = meta.volcVoice;
    if (meta.phoneVoice) phoneVoice.value = meta.phoneVoice;
    if (meta.systemPrompt) systemPrompt.value = meta.systemPrompt;
    if (meta.speakingStyle) speakingStyle.value = meta.speakingStyle;
    if (meta.isWebSearchEnabled !== undefined) isWebSearchEnabled.value = meta.isWebSearchEnabled;
    if (meta.isVoiceReplyEnabled !== undefined) isVoiceReplyEnabled.value = meta.isVoiceReplyEnabled;

    nextTick(() => {
        isInternalUpdate.value = false;
    });
};

// Sync Settings
const isInternalUpdate = ref(false);

const syncSettingsToHistory = async (showToastMsg = true) => {
    if (!currentAvatarUrl.value) return;

    try {
        await fetch('/history', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: currentAvatarUrl.value,
                meta: {
                    fit: avatarFit.value,
                    scale: avatarScale.value,
                    ttsProvider: ttsProvider.value,
                    volcVoice: volcVoice.value,
                    phoneVoice: phoneVoice.value,
                    systemPrompt: systemPrompt.value,
                    speakingStyle: speakingStyle.value,
                    isWebSearchEnabled: isWebSearchEnabled.value,
                    isVoiceReplyEnabled: isVoiceReplyEnabled.value
                }
            })
        });
        if (showToastMsg) {
            showToast({ message: '设置已保存', position: 'bottom' });
            await loadHistory();
        }
    } catch (e) {
        console.error("Failed to sync settings", e);
    }
};

let debounceTimer: any = null;

// Actions
const deleteAvatar = async (url: string, event: Event) => {
    event.stopPropagation();
    try {
        const response = await fetch('/history', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (response.ok) {
            avatarHistory.value = await response.json();
            if (currentAvatarUrl.value === url && avatarHistory.value.length > 0) {
                selectAvatar(avatarHistory.value[0]);
            } else if (avatarHistory.value.length === 0) {
                currentAvatarUrl.value = '';
            }
        }
    } catch (e) {
        console.error("Failed to delete avatar", e);
    }
};

const importHistory = async (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/history/import', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(`成功导入 ${result.count} 条记录`);
            loadHistory();
        } else {
            showToast('导入失败');
        }
    } catch (e) {
        showToast('导入出错');
    } finally {
        input.value = '';
    }
};

// Upload Logic
const fileInput = ref<HTMLInputElement | null>(null);
const avatarFileInput = ref<HTMLInputElement | null>(null);
const isUploading = ref(false);

const triggerUpload = () => {
    fileInput.value?.click();
};

const triggerAvatarUpload = () => {
    avatarFileInput.value?.click();
};

const triggerAiAvatarUpload = () => {
    aiAvatarFileInput.value?.click();
};

const handleAvatarUpload = async (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    isUploading.value = true;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload_avatar', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            await loadHistory();
            showToast('头像上传成功');
        } else {
            try {
                const err = await response.json();
                showToast(`上传失败: ${err.message}`);
            } catch {
                showToast('上传失败');
            }
        }
    } catch (e) {
        console.error("Upload error", e);
        showToast('上传出错');
    } finally {
        isUploading.value = false;
        input.value = '';
    }
};

const handleAiAvatarUpload = async (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    isUploading.value = true;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload_ai_avatar', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            aiAvatarUrl.value = result.url;

            // Save to config
            await fetch('/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ aiAvatarUrl: result.url })
            });

            showToast('AI 头像上传成功');
        } else {
            try {
                const err = await response.json();
                showToast(`上传失败: ${err.message}`);
            } catch {
                showToast('上传失败');
            }
        }
    } catch (e) {
        console.error("Upload error", e);
        showToast('上传出错');
    } finally {
        isUploading.value = false;
        input.value = '';
    }
};

const handleFileUpload = async (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    isUploading.value = true;
    
    const formData = new FormData();
    formData.append('image', file);
    formData.append('avatar_fit', avatarFit.value);
    formData.append('avatar_scale', avatarScale.value.toString());
    
    try {
        const response = await fetch('/animate', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            // Reload history to get the new avatar
            await loadHistory();
            showToast('上传并生成成功');
        } else {
            const err = await response.json();
            showToast(`生成失败: ${err.message}`);
        }
    } catch (e) {
        console.error("Upload error", e);
        showToast('上传出错');
    } finally {
        isUploading.value = false;
        input.value = '';
    }
};

onMounted(() => {
    loadConfig();
    loadHistory();
    // Poll for history updates to keep list fresh
    // setInterval(() => {
    //     loadHistory();
    // }, 5000);
});
</script>

<template>
  <div class="min-h-screen bg-slate-50 font-sans text-slate-800">
      <!-- Header -->
      <header class="bg-white border-b border-slate-200 sticky top-0 z-10 px-6 py-4 flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-3">
              <h1 class="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">数字人后台管理</h1>
              <span class="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full font-medium">Admin</span>
          </div>
          <router-link to="/" class="flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 transition-colors">
              <ArrowLeftOnRectangleIcon class="w-4 h-4" />
              <span>返回前台</span>
          </router-link>
      </header>

      <main class="max-w-5xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          <!-- Left Column: History & Upload -->
          <div class="lg:col-span-7 space-y-6">
              <!-- Upload Card -->
              <div class="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                  <h2 class="text-lg font-bold mb-4 text-slate-700">形象管理</h2>

                  <div class="space-y-4">
                      <!-- Upload Digital Human Avatar -->
                      <div class="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border-2 border-dashed border-blue-200 hover:border-blue-400 hover:shadow-md transition-all flex flex-col items-center justify-center gap-3 cursor-pointer group" @click="triggerAvatarUpload">
                          <input type="file" ref="avatarFileInput" class="hidden" accept="image/*,video/*" @change="handleAvatarUpload" />
                          <div class="w-14 h-14 bg-white rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform text-blue-500">
                              <CameraIcon v-if="!isUploading" class="w-7 h-7" />
                              <div v-else class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                          </div>
                          <div class="text-center">
                              <p class="font-bold text-slate-700 text-base">生成数字人</p>
                              <p class="text-sm text-slate-500 mt-1">支持图片自动生成动画 / 直接上传视频</p>
                          </div>
                      </div>

                      <!-- Upload AI Avatar -->
                      <div class="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-6 border-2 border-dashed border-purple-200 hover:border-purple-400 hover:shadow-md transition-all flex flex-col items-center justify-center gap-3 cursor-pointer group" @click="triggerAiAvatarUpload">
                          <input type="file" ref="aiAvatarFileInput" class="hidden" accept="image/*" @change="handleAiAvatarUpload" />
                          <div class="w-14 h-14 bg-white rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform text-purple-500 overflow-hidden">
                              <img v-if="aiAvatarUrl && !isUploading" :src="aiAvatarUrl" class="w-full h-full object-cover" alt="AI Avatar" />
                              <CameraIcon v-else-if="!isUploading" class="w-7 h-7" />
                              <div v-else class="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
                          </div>
                          <div class="text-center">
                              <p class="font-bold text-slate-700 text-base">上传 AI 头像</p>
                              <p class="text-sm text-slate-500 mt-1">聊天界面 AI 消息旁边的头像图标</p>
                          </div>
                      </div>
                  </div>
              </div>

              <!-- History Grid -->
              <div class="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                  <div class="flex justify-between items-center mb-4">
                      <h2 class="text-lg font-bold text-slate-700">历史记录</h2>
                      <label class="text-sm text-blue-600 cursor-pointer hover:underline">
                          导入 JSON
                          <input type="file" accept=".json" class="hidden" @change="importHistory" />
                      </label>
                  </div>
                  
                  <div v-if="avatarHistory.length === 0" class="text-center py-10 text-slate-400">
                      暂无历史记录
                  </div>
                  
                  <div class="grid grid-cols-3 sm:grid-cols-4 gap-4">
                      <div 
                          v-for="(item, index) in avatarHistory" 
                          :key="index"
                          class="relative aspect-square rounded-xl overflow-hidden border-2 cursor-pointer transition-all group"
                          :class="[
                              index === 0 ? 'ring-2 ring-blue-100 border-blue-500' : 'border-transparent hover:border-slate-300',
                              item && (typeof item === 'string' ? item : item.url) === currentAvatarUrl && index !== 0 ? 'border-amber-400 ring-2 ring-amber-100' : ''
                          ]"
                          @click="selectAvatar(item)"
                      >
                          <video 
                              :src="typeof item === 'string' ? item : item.url" 
                              class="w-full h-full object-cover bg-slate-100" 
                              muted 
                              playsinline
                          ></video>
                          
                          <!-- Overlay -->
                          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-start justify-end p-1">
                              <button 
                                 @click="deleteAvatar(typeof item === 'string' ? item : item.url, $event)"
                                 class="bg-white/90 hover:bg-red-500 hover:text-white text-slate-500 p-1 rounded-full shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                                 title="删除"
                              >
                                 <XMarkIcon class="w-3.5 h-3.5" />
                              </button>
                          </div>
                          
                          <!-- Active Badge (Only for the first item which is truly active) -->
                          <div v-if="index === 0" class="absolute bottom-0 inset-x-0 bg-blue-500/80 text-white text-[10px] text-center py-0.5 backdrop-blur-sm">
                              当前使用
                          </div>
                          <!-- Editing Badge (If selected but not active/first) -->
                          <div v-else-if="item && (typeof item === 'string' ? item : item.url) === currentAvatarUrl" class="absolute bottom-0 inset-x-0 bg-amber-500/80 text-white text-[10px] text-center py-0.5 backdrop-blur-sm">
                              待保存
                          </div>
                      </div>
                  </div>
              </div>
          </div>

          <!-- Right Column: Settings Form -->
          <div class="lg:col-span-5 space-y-6">
              <div class="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 sticky top-24">
                  <h2 class="text-lg font-bold mb-6 text-slate-700">参数配置</h2>
                  
                  <div class="space-y-6">
                      <!-- Display Mode -->
                      <div>
                          <label class="block text-sm font-medium text-slate-700 mb-2">形象显示方式</label>
                          <div class="grid grid-cols-2 gap-2 bg-slate-50 p-1 rounded-xl">
                              <button 
                                 @click="avatarFit = 'cover'"
                                 class="py-2 rounded-lg text-sm font-medium transition-all"
                                 :class="avatarFit === 'cover' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                              >全身 (Cover)</button>
                              <button 
                                 @click="avatarFit = 'contain'"
                                 class="py-2 rounded-lg text-sm font-medium transition-all"
                                 :class="avatarFit === 'contain' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                              >半身 (Contain)</button>
                          </div>
                          <p class="text-xs text-slate-400 mt-1.5">决定数字人在屏幕中的填充方式。</p>
                      </div>

                      <!-- Scale -->
                      <div>
                          <label class="block text-sm font-medium text-slate-700 mb-2">人物缩放 ({{ Number(avatarScale).toFixed(2) }}x)</label>
                          <div class="flex items-center gap-4">
                              <van-slider 
                                  v-model="avatarScale" 
                                  :min="0.5" 
                                  :max="2.0" 
                                  :step="0.05" 
                                  bar-height="4px"
                                  active-color="#3b82f6"
                                  @update:model-value="(val) => avatarScale = Number(val)"
                                  class="flex-1"
                              />
                              <van-stepper 
                                  v-model="avatarScale" 
                                  :min="0.5" 
                                  :max="2.0" 
                                  :step="0.05" 
                                  :decimal-length="2"
                                  button-size="28px"
                                  class="flex-none"
                                  @change="(val) => avatarScale = Number(val)"
                              />
                          </div>
                      </div>

                      <div class="border-t border-slate-100 my-4"></div>

                      <!-- Voice Engine -->
                          <div class="mb-4">
                              <label class="block text-sm font-medium text-slate-700 mb-2">语音合成引擎</label>
                              <div class="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-lg">
                                  <button 
                                      v-for="provider in ['edge', 'volcengine']" 
                                      :key="provider"
                                      class="py-1.5 text-sm font-medium rounded-md transition-all"
                                      :class="ttsProvider === provider ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                                      @click="ttsProvider = provider"
                                  >
                                      {{ provider === 'edge' ? '微软 Edge' : '火山引擎' }}
                                  </button>
                              </div>
                          </div>

                          <!-- Volcengine Voice Selection -->
                          <div v-if="ttsProvider === 'volcengine'" class="mb-4 animate-fade-in">
                              <label class="block text-sm font-medium text-slate-700 mb-2">火山音色</label>
                              <div class="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto pr-1 custom-scrollbar">
                                  <div
                                      v-for="voice in volcVoices"
                                      :key="voice.id"
                                      class="flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all hover:border-blue-300"
                                      :class="volcVoice === voice.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'"
                                      @click="volcVoice = voice.id"
                                  >
                                      <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-xs overflow-hidden">
                                          <!-- Simple Avatar Placeholder -->
                                          <img v-if="voice.name.includes('女') || voice.id.includes('female')" src="https://api.dicebear.com/7.x/micah/svg?seed=Molly" />
                                          <img v-else src="https://api.dicebear.com/7.x/micah/svg?seed=Max" />
                                      </div>
                                      <div class="flex-1 min-w-0">
                                          <div class="text-xs font-medium truncate" :class="volcVoice === voice.id ? 'text-blue-700' : 'text-slate-700'">{{ voice.name }}</div>
                                      </div>
                                  </div>
                              </div>
                          </div>

                          <!-- Phone Mode Voice Selection -->
                          <div class="mb-4">
                              <label class="block text-sm font-medium text-slate-700 mb-2">通话音色（实时对话）</label>
                              <div class="grid grid-cols-2 gap-2">
                                  <div
                                      v-for="voice in phoneVoices"
                                      :key="voice.id"
                                      class="flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all hover:border-green-300"
                                      :class="phoneVoice === voice.id ? 'border-green-500 bg-green-50' : 'border-slate-200 bg-white'"
                                      @click="phoneVoice = voice.id"
                                  >
                                      <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-xs overflow-hidden">
                                          <img v-if="voice.name.includes('女')" src="https://api.dicebear.com/7.x/micah/svg?seed=Luna" />
                                          <img v-else src="https://api.dicebear.com/7.x/micah/svg?seed=Leo" />
                                      </div>
                                      <div class="flex-1 min-w-0">
                                          <div class="text-xs font-medium truncate" :class="phoneVoice === voice.id ? 'text-green-700' : 'text-slate-700'">{{ voice.name }}</div>
                                      </div>
                                  </div>
                              </div>
                          </div>

                      <div class="border-t border-slate-100 my-4"></div>

                      <!-- Toggles -->
                      <div class="space-y-4">
                          <div class="flex items-center justify-between">
                              <div>
                                  <div class="text-sm font-medium text-slate-700">联网搜索</div>
                                  <div class="text-xs text-slate-400">允许 AI 搜索实时信息</div>
                              </div>
                              <van-switch v-model="isWebSearchEnabled" size="22px" active-color="#3b82f6" />
                          </div>
                          
                          <div class="flex items-center justify-between">
                              <div>
                                  <div class="text-sm font-medium text-slate-700">语音回复</div>
                                  <div class="text-xs text-slate-400">自动朗读 AI 的回复内容</div>
                              </div>
                              <van-switch v-model="isVoiceReplyEnabled" size="22px" active-color="#3b82f6" />
                          </div>
                      </div>

                      <div class="border-t border-slate-100 my-4"></div>

                      <!-- Role Settings -->
                      <div class="space-y-4">
                          <div>
                              <label class="block text-sm font-medium text-slate-700 mb-2">角色设定</label>
                              <textarea
                                  v-model="systemPrompt"
                                  placeholder="定义AI的角色和性格..."
                                  class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-400 focus:border-transparent resize-none"
                                  rows="3"
                              ></textarea>
                          </div>

                          <div>
                              <label class="block text-sm font-medium text-slate-700 mb-2">说话风格</label>
                              <textarea
                                  v-model="speakingStyle"
                                  placeholder="定义AI的说话方式和风格..."
                                  class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-400 focus:border-transparent resize-none"
                                  rows="2"
                              ></textarea>
                          </div>
                      </div>

                      <!-- Manual Save Button -->
                      <div class="pt-4 space-y-2">
                          <button
                              @click="syncSettingsToHistory(true)"
                              class="w-full py-2.5 rounded-xl bg-blue-600 text-white font-medium shadow-md hover:bg-blue-700 active:scale-95 transition-all flex items-center justify-center gap-2"
                          >
                              <span>保存当前配置</span>
                          </button>

                          <button
                              @click="showChatHistory = true; loadConversations()"
                              class="w-full py-2.5 rounded-xl bg-green-600 text-white font-medium shadow-md hover:bg-green-700 active:scale-95 transition-all flex items-center justify-center gap-2"
                          >
                              <span>查看聊天记录</span>
                          </button>
                      </div>
                  </div>
              </div>
          </div>
      </main>

      <!-- Chat History Modal -->
      <div v-if="showChatHistory" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" @click.self="showChatHistory = false">
          <div class="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[85vh] overflow-hidden flex">
              <!-- Left Sidebar: Conversation List -->
              <div class="w-80 border-r border-slate-200 flex flex-col bg-slate-50">
                  <div class="p-4 border-b border-slate-200">
                      <h3 class="text-sm font-bold text-slate-700">对话列表</h3>
                  </div>
                  <div class="flex-1 overflow-y-auto">
                      <div v-if="conversations.length === 0" class="text-center py-8 text-slate-400 text-sm">
                          暂无对话
                      </div>
                      <div v-else class="p-2 space-y-1">
                          <div
                              v-for="conv in conversations"
                              :key="conv.id"
                              class="group relative p-3 rounded-lg cursor-pointer transition-all hover:bg-white"
                              :class="selectedConversation?.id === conv.id ? 'bg-white shadow-sm border border-blue-200' : 'hover:shadow-sm'"
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
                                  <button
                                      @click.stop="deleteConversation(conv.id)"
                                      class="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded transition-all"
                                      title="删除对话"
                                  >
                                      <XMarkIcon class="w-4 h-4 text-red-500" />
                                  </button>
                              </div>
                          </div>
                      </div>
                  </div>
              </div>

              <!-- Right Panel: Messages -->
              <div class="flex-1 flex flex-col">
                  <!-- Header -->
                  <div class="flex items-center justify-between p-6 border-b border-slate-200">
                      <h2 class="text-xl font-bold text-slate-800">
                          {{ selectedConversation ? (selectedConversation.title || '新对话') : '聊天记录' }}
                      </h2>
                      <button @click="showChatHistory = false" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">
                          <XMarkIcon class="w-5 h-5 text-slate-500" />
                      </button>
                  </div>

                  <!-- Messages -->
                  <div class="flex-1 overflow-y-auto p-6">
                      <div v-if="!selectedConversation" class="text-center py-12 text-slate-400">
                          请从左侧选择一个对话
                      </div>
                      <div v-else-if="conversationMessages.length === 0" class="text-center py-12 text-slate-400">
                          该对话暂无消息
                      </div>
                      <div v-else class="space-y-4">
                          <div v-for="(msg, index) in conversationMessages" :key="index" class="flex gap-3" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                              <div class="max-w-[70%] rounded-2xl px-4 py-3" :class="msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-800'">
                                  <div class="text-sm whitespace-pre-wrap">{{ msg.content }}</div>
                                  <div class="text-xs mt-1 opacity-60">{{ new Date(msg.timestamp * 1000).toLocaleString() }}</div>
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
      </div>
  </div>
</template>
