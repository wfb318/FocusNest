<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAppearance } from '../stores/appearance'
import { DEFAULT_STYLE, styleVariables } from '../utils/appearanceStyle'
import { BACKGROUND_ACCEPT } from '../utils/backgroundMedia'

const appearance = useAppearance()
const { backgroundUrl, posterUrl, backgroundKind, paused, playbackBlocked, stylePreferences, veil, busy, error, notice } = appearance
const sampleUrl = computed(() => backgroundKind.value === 'video' || (backgroundKind.value === 'gif' && paused.value) ? posterUrl.value : backgroundUrl.value)
const picker = ref<HTMLInputElement | null>(null)
const draftVeil = ref(veil.value)
const draftStyle = reactive({ ...stylePreferences.value })
watch(stylePreferences, value => { Object.assign(draftStyle, value) })
const stylePreview = computed(() => styleVariables(draftStyle))
async function resetStyle() { Object.assign(draftStyle, DEFAULT_STYLE); await appearance.saveStyle(draftStyle) }
watch(veil, value => { draftVeil.value = value })
async function selectMedia(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) await appearance.setBackground(file)
  input.value = ''
}
</script>

<template>
  <section class="panel appearance-panel" aria-labelledby="appearance-title">
    <div class="appearance-heading"><div><span class="eyebrow">MAKE IT YOURS</span><h2 id="appearance-title">背景与外观</h2></div><span class="appearance-badge">磨砂玻璃</span></div>
    <p class="muted">选择图片、GIF 或静音循环视频，让工作台更有自己的感觉。</p>
    <div class="background-sample" :style="sampleUrl ? { backgroundImage: `url('${sampleUrl}')` } : {}"><div :style="{ backgroundColor: `rgba(244, 247, 242, ${draftVeil})` }"><span class="sample-glass">你的专注空间</span></div></div>
    <input ref="picker" class="image-picker" type="file" :accept="BACKGROUND_ACCEPT" aria-label="选择背景文件" :disabled="busy" @change="selectMedia">
    <div class="appearance-buttons"><button type="button" class="quiet" :disabled="busy" @click="picker?.click()">{{ busy ? '处理中…' : backgroundUrl ? '更换背景文件' : '选择背景文件' }}</button><button type="button" class="quiet" :disabled="busy || !backgroundUrl" @click="appearance.reset">恢复默认背景</button><button v-if="backgroundUrl && backgroundKind !== 'image'" type="button" class="quiet" :disabled="busy" @click="appearance.savePaused(playbackBlocked ? false : !paused)">{{ playbackBlocked ? '重试播放' : paused ? '播放动态背景' : '暂停动态背景' }}</button></div>
    <p v-if="backgroundKind === 'video'" class="muted appearance-hint">视频背景静音循环播放，页面不可见时暂停。上方示例显示视频封面。</p>
    <p v-if="playbackBlocked" class="form-error" role="alert">浏览器未能播放背景视频，暂显示封面。可点击重试，或换用 H.264 MP4 / WebM。</p>
    <label for="background-veil">背景柔化 <span>{{ Math.round(draftVeil * 100) }}%</span></label>
    <input id="background-veil" v-model.number="draftVeil" type="range" min="0.1" max="0.8" step="0.01" :disabled="busy" @change="appearance.saveVeil(draftVeil)">
    <p class="muted appearance-hint">向右调节，让背景更柔和、文字更清晰。图片支持 JPG、PNG、WebP、GIF，最大 10 MB；视频支持 MP4、WebM、OGV，最大 50 MB，需浏览器支持其编码。GIF/视频像素数不超过 3840×2160，可暂停并记住状态。背景文件仅保存在此浏览器；清除网站数据后需重新选择，同一浏览器下的账号共用此外观。</p>
    <section class="style-settings" aria-label="文字与磨砂样式">
      <h3>文字与磨砂样式</h3><p class="muted appearance-hint">先预览，再点击保存。导航和页面标题始终保持透明底。</p>
      <label for="appearance-font-size">字号比例 <span>{{ Math.round(draftStyle.fontScale * 100) }}%</span></label><input id="appearance-font-size" v-model.number="draftStyle.fontScale" type="range" min="0.8" max="1.5" step="0.05" :disabled="busy">
      <div class="style-colors"><div><label for="appearance-text-color">文字颜色</label><input id="appearance-text-color" v-model="draftStyle.textColor" type="color" :disabled="busy"><code>{{ draftStyle.textColor }}</code></div><div><label for="appearance-glass-color">磨砂背景颜色</label><input id="appearance-glass-color" v-model="draftStyle.glassColor" type="color" :disabled="busy"><code>{{ draftStyle.glassColor }}</code></div></div>
      <div class="style-sample" :style="stylePreview"><strong>FocusNest · 样式预览</strong><p>记录、计划、阅读，让背景与文字保持自己的风格。</p></div>
      <div class="appearance-buttons"><button type="button" class="quiet" :disabled="busy" @click="appearance.saveStyle(draftStyle)">保存文字与磨砂样式</button><button type="button" class="quiet" :disabled="busy" @click="resetStyle">恢复默认文字与磨砂</button></div>
    </section>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p><p v-if="notice" class="form-success" role="status">{{ notice }}</p>
  </section>
</template>

<style scoped>
.appearance-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.appearance-heading h2{margin:8px 0}.appearance-badge{font-size:calc(12px * var(--ui-font-scale,1));color:var(--text-primary,#263c34);padding:7px 12px;border:1px solid #ffffffb3;border-radius:20px;background:#ffffff80}.background-sample{margin:20px 0;border-radius:14px;overflow:hidden;background:radial-gradient(ellipse at 20% 15%,#b9d8cb,transparent 60%),linear-gradient(130deg,#dfebe2,#dbe5ed 55%,#f1e8da);background-position:center;background-size:cover}.background-sample>div{display:grid;place-items:center;height:170px}.sample-glass{padding:18px 28px;border:1px solid #ffffffbd;border-radius:12px;background:rgba(var(--glass-rgb),.10);backdrop-filter:blur(2px);color:var(--text-primary,#263c34);box-shadow:0 8px 28px #263c3410}.image-picker{position:absolute;width:1px;height:1px;opacity:0;overflow:hidden}.appearance-buttons{display:flex;gap:12px;flex-wrap:wrap}.quiet{padding:10px 16px;border-radius:9px;color:var(--text-primary,#263c34)}.appearance-panel label{display:flex;justify-content:space-between;margin:26px 0 10px;font-size:calc(13px * var(--ui-font-scale,1))}.appearance-panel input[type=range]{width:100%;accent-color:#39765c;cursor:pointer}.appearance-hint{font-size:calc(12px * var(--ui-font-scale,1));margin-bottom:0}
.style-settings{border-top:1px solid rgba(127,127,127,.2);margin-top:26px;padding-top:14px}.style-settings h3{font-size:calc(16px * var(--ui-font-scale,1));font-weight:550}.style-colors{display:grid;grid-template-columns:1fr 1fr;gap:20px}.style-colors input[type=color]{display:block;width:64px;height:38px;padding:3px;border:1px solid #a0b4a8;border-radius:6px;background:transparent;cursor:pointer}.style-colors code{font-size:calc(12px * var(--ui-font-scale,1));display:block;margin-top:6px}.style-sample{color:var(--text-primary);background:rgba(var(--glass-rgb),.14);backdrop-filter:blur(2px);border:1px solid rgba(var(--glass-rgb),.2);padding:18px;border-radius:10px;margin:22px 0;font-size:calc(14px * var(--ui-font-scale,1));line-height:1.8}.style-sample p{color:inherit;font-size:inherit;margin-bottom:0}
</style>
