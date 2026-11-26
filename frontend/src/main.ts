import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElAlert, ElButton, ElDescriptions, ElDescriptionsItem, ElTag } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/descriptions/style/css'
import 'element-plus/es/components/descriptions-item/style/css'
import 'element-plus/es/components/tag/style/css'
import './assets/main.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia()).use(router)
app.component('ElAlert', ElAlert)
app.component('ElButton', ElButton)
app.component('ElDescriptions', ElDescriptions)
app.component('ElDescriptionsItem', ElDescriptionsItem)
app.component('ElTag', ElTag)
app.mount('#app')
