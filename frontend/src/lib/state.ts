import { reactive } from 'vue'

export default reactive({
  current_sysname: '0-base',
  options: {
    showGrid: true,
    showBase: window.innerWidth > 768
  }
})
