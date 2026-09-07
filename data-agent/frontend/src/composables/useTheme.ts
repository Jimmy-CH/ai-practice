import { ref, watch } from 'vue'

const isDark = ref(localStorage.getItem('theme') === 'dark')

export function useTheme() {
  function applyTheme(dark: boolean) {
    document.documentElement.classList.toggle('dark', dark)
  }

  function toggleTheme() {
    isDark.value = !isDark.value
  }

  applyTheme(isDark.value)

  watch(isDark, (val) => {
    applyTheme(val)
    localStorage.setItem('theme', val ? 'dark' : 'light')
  })

  return { isDark, toggleTheme }
}
