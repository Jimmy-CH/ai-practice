/**
 * YtoNotify - 推广运营通知 SDK
 * 纯原生 JS/CSS 实现，无框架依赖
 * 兼容：Web 浏览器、桌面 PC 应用（Electron / NW.js / WebView）、CommonJS / AMD
 *
 * 用法：
 *   // Web 端：<script> 标签引入
 *   <script src="/yto-notify/csp-notify.js"></script>
 *   <script>
 *     YtoNotify.init({
 *       baseUrl: 'http://10.130.10.229/',
 *       system: '星辰',
 *       usercode: '03420092',
 *       functionTypes: [30]
 *     })
 *   </script>
 *
 *   // 桌面端（Electron / Node）：require 引入
 *   var YtoNotify = require('./yto-notify/csp-notify')
 *   YtoNotify.init({ ... })
 *
 * 扩展新场景：
 *   YtoNotify.register(50, MyNewHandler)
 */
;(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    // CommonJS / Node / Electron renderer
    module.exports = factory()
  } else if (typeof define === 'function' && define.amd) {
    // AMD
    define(factory)
  } else {
    // Browser global / WebView / 桌面应用 webview
    root.YtoNotify = factory()
  }
})(typeof globalThis !== 'undefined' ? globalThis
  : typeof window !== 'undefined' ? window
  : typeof self !== 'undefined' ? self
  : typeof global !== 'undefined' ? global
  : this,
function () {
  'use strict'

  // ======================== 常量 ========================
  var TOKEN = 'ca3d19071bd723289916348961922575031d8d02'

  // ======================== CSS 样式（注入到 head） ========================
  var CSS_TEXT = [
    /* ---------- 遮罩层 ---------- */
    '.yto-notify-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);z-index:99999;display:flex;align-items:center;justify-content:center;animation:ytoFadeIn .25s ease}',
    '@keyframes ytoFadeIn{from{opacity:0}to{opacity:1}}',

    /* ---------- 弹框容器 ---------- */
    '.yto-notify-dialog{background:#fff;border-radius:14px;box-shadow:0 2px 12px 0 rgba(0,0,0,.1);display:flex;flex-direction:column;overflow:hidden;position:relative;max-width:92vw;max-height:92vh;animation:ytoScaleIn .25s ease}',
    '@keyframes ytoScaleIn{from{transform:scale(.92);opacity:0}to{transform:scale(1);opacity:1}}',

    /* ---------- 底部操作区（弹框外部） ---------- */
    '.yto-notify-wrapper{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center}',
    '.yto-notify-footer{display:flex;flex-direction:column;align-items:center;padding:10px 0 0;gap:20px}',
    '.yto-notify-close-btn{padding:7px 28px;border:none;border-radius:20px;font-size:14px;color:#fff;background:var(--yto-primary,#9547ec);cursor:pointer;transition:opacity .2s;outline:none;text-align:center;font-family:sans-serif}',
    '.yto-notify-close-btn:hover{opacity:.85}',
    '.yto-notify-close-btn.yto-disabled{cursor:not-allowed;background:rgba(255,255,255,0.1);border: 1px solid #FFFFFF;}',

    /* ---------- 轮播区域 ---------- */
    '.yto-notify-body{flex:1;overflow:hidden;padding:0;min-height:0;position:relative}',
    '.yto-carousel{position:relative;width:100%;height:100%;overflow:hidden}',
    '.yto-slide{position:absolute;top:0;left:0;width:100%;height:100%;z-index:0;transition:transform .5s ease;transform:translateX(100%);display:flex;align-items:center;justify-content:center}',
    '.yto-slide.yto-active{transform:translateX(0);z-index:1}',
    '.yto-slide.yto-slide-left{transform:translateX(-100%)}',
    '.yto-slide.yto-no-transition{transition:none}',
    '.yto-slide img{max-width:100%;max-height:100%;object-fit:contain;display:block;user-select:none;-webkit-user-drag:none}',

    /* ---------- 左右箭头 ---------- */
    '.yto-arrow{position:absolute;top:50%;transform:translateY(-50%);width:36px;height:36px;display:flex;align-items:center;justify-content:center;background:rgba(31,45,61,.3);color:#fff;border:none;border-radius:50%;cursor:pointer;z-index:10;transition:all .3s ease;outline:none;padding:0;opacity:0}',
    '.yto-carousel:hover .yto-arrow{opacity:1}',
    '.yto-arrow:hover{background:rgba(31,45,61,.5)}',
    '.yto-arrow svg{width:14px;height:14px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}',
    '.yto-arrow-left{left:12px}',
    '.yto-arrow-right{right:12px}',

    /* ---------- 指示器 ---------- */
    '.yto-indicators{display:flex;gap:8px;justify-content:center}',
    '.yto-dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.6);cursor:pointer;transition:all .2s;border:none;outline:none;padding:0}',
    '.yto-dot.yto-dot-active{background:#fff;width:16px;border-radius:3px;}',

    /* ---------- 图文公告弹框 ---------- */
    '.yto-article-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);z-index:99999;display:flex;align-items:center;justify-content:center;animation:ytoFadeIn .25s ease}',
    '.yto-article-dialog{background:#fff;border-radius:14px;box-shadow:0 2px 12px 0 rgba(0,0,0,.1);display:flex;flex-direction:column;overflow:hidden;position:relative;max-width:90%;max-height:90%;animation:ytoScaleIn .25s ease}',
    '.yto-article-title{flex-shrink:0;text-align:center;font-size:18px;font-weight:600;color:#151719;padding:16px 20px 12px;line-height:1.4}',
    '.yto-article-body{flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0;padding:14px 0}',
    '.yto-article-content{flex:1;min-height:0;overflow-y:auto;padding:0 14px;line-height:1.7;font-size:14px;color:#333}',
    '.yto-article-content img{max-width:100%;display:block;height:auto}',
    '.yto-article-footer{padding:14px;padding-top:0;flex-shrink:0;display:flex;flex-direction:column;align-items:center}',
    '.yto-article-countdown{font-size:14px;color:#90979E;margin-bottom:20px;text-align:center}',
    '.yto-article-countdown-second{font-weight:600;color:#52585F;background:#E0E7ED;border-radius:4px;padding:2px 5px}',
    '.yto-article-btns{display:flex;justify-content:center;align-items:center;gap:10px;flex-wrap:wrap}',
    '.yto-article-btn{padding:7px 20px;border:none;border-radius:20px;font-size:14px;cursor:pointer;transition:opacity .2s;color:#fff;background:var(--yto-primary,#9547ec);outline:none;font-family:sans-serif}',
    '.yto-article-btn:hover{opacity:.85}',
    '.yto-article-btn.yto-article-btn-default{color:#606266;background:#e4e7ed}',
    '.yto-article-btn.yto-article-btn-default:hover{opacity:.85}',
    '.yto-article-close-btn{color:#606266;background:#fff;border:1px solid #DCDFE6}',
    '.yto-article-close-btn:hover{color:#9547EC;border-color:#DFC8F9;background-color:#F4EDFD;opacity:1}',
    '.yto-article-btn.yto-disabled{cursor:not-allowed;opacity:.55;pointer-events:none}',

    /* ---------- 跑马灯 ---------- */
    '.yto-marquee-bar{position:fixed;left:0;width:100%;height:40px;display:flex;align-items:center;padding:0 10%;background:#fff8e6;border-bottom:1px solid #ffe58f;z-index:99998;font-family:sans-serif}',
    '.yto-marquee-top{top:0}',
    '.yto-marquee-bottom{bottom:0;border-bottom:none;border-top:1px solid #ffe58f}',
    '.yto-marquee-icon{flex-shrink:0;display:flex;align-items:center;margin-right:8px}',
    '.yto-marquee-icon svg{width:20px;height:20px;fill:var(--yto-primary,#9547ec)}',
    '.yto-marquee-container{flex:1;overflow:hidden;position:relative;height:100%;min-width:0}',
    '.yto-marquee-scroll{display:inline-flex;white-space:nowrap}',
    '.yto-marquee-text{white-space:nowrap;font-size:14px;color:#303133;line-height:40px;display:inline-block}',
    '.yto-marquee-text-link{cursor:pointer;pointer-events:auto}',
    '.yto-marquee-text-link:hover{color:var(--yto-primary,#9547ec)}',
    '.yto-marquee-close{flex-shrink:0;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;cursor:pointer;font-size:14px;color:#909399;border:none;background:none;outline:none;padding:0;margin-left:8px;transition:color .2s;font-family:sans-serif;pointer-events:auto}',
    '.yto-marquee-close:hover{color:#606266}',

    /* ---------- 浮窗通知 ---------- */
    '.yto-float-card{position:fixed;right:30px;width:136px;height:166px;background:#fff;border-radius:16px;box-shadow:0px 2px 10px 0px #E1E7F2;padding:8px;font-family:sans-serif;pointer-events:auto;z-index:99997;opacity:0;transform:translateY(30px);transition:opacity .5s ease,transform .5s ease}',
    '.yto-float-card.yto-float-show{opacity:1;transform:translateY(0)}',
    '.yto-float-card.yto-float-hide{opacity:0;transform:translateY(30px)}',
    '.yto-float-card.yto-float-no-animate{transition:none}',
    '.yto-float-header{display:flex;align-items:center;gap:8px;margin-bottom:10px}',
    '.yto-float-text{flex:1;min-width:0;font-size:14px;color:#151719;text-align:center;height:20px;line-height:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.yto-float-close{flex-shrink:0;height:20px;cursor:pointer;font-size:12px;color:#666;line-height:20px;padding:0;background:none;border:none;outline:none;font-family:sans-serif}',
    '.yto-float-close:hover{color:#333}',
    '.yto-float-img-wrap{width:100%;border-radius:6px;display:flex;align-items:center;justify-content:center;overflow:hidden}',
    '.yto-float-img-wrap img{height:120px;width:auto;max-width:100%;display:block;user-select:none;-webkit-user-drag:none}',
    '.yto-float-img-placeholder{width:100%;height:120px;line-height:120px;text-align:center;color:#909399;font-size:14px}',
    '.yto-float-link{cursor:pointer}',
    '.yto-float-link:hover{opacity:.85}',

    /* ---------- 轮播图 ---------- */
    '.yto-banner-wrap{position:relative;width:100%;height:100%;overflow:hidden;font-family:sans-serif}',
    '.yto-banner-slide{position:absolute;top:0;left:0;width:100%;height:100%;z-index:0;transition:transform .5s ease;transform:translateX(100%);display:flex;align-items:center;justify-content:center}',
    '.yto-banner-slide.yto-banner-active{transform:translateX(0);z-index:1}',
    '.yto-banner-slide.yto-banner-slide-left{transform:translateX(-100%)}',
    '.yto-banner-slide.yto-banner-no-transition{transition:none}',
    '.yto-banner-slide img{width:100%;height:100%;display:block;user-select:none;-webkit-user-drag:none}',
    '.yto-banner-arrow{position:absolute;top:50%;transform:translateY(-50%);width:36px;height:36px;display:flex;align-items:center;justify-content:center;background:rgba(31,45,61,.3);color:#fff;border:none;border-radius:50%;cursor:pointer;z-index:10;transition:all .3s ease;outline:none;padding:0;opacity:0}',
    '.yto-banner-wrap:hover .yto-banner-arrow{opacity:1}',
    '.yto-banner-arrow:hover{background:rgba(31,45,61,.5)}',
    '.yto-banner-arrow svg{width:14px;height:14px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}',
    '.yto-banner-arrow-left{left:12px}',
    '.yto-banner-arrow-right{right:12px}',
    '.yto-banner-dots{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:10}',
    '.yto-banner-dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.6);cursor:pointer;transition:all .2s;border:none;outline:none;padding:0}',
    '.yto-banner-dot.yto-banner-dot-active{background:#fff;width:16px;border-radius:3px}'
  ].join('\n')

  function injectCSS () {
    if (typeof document === 'undefined') return
    if (document.getElementById('yto-notify-style')) return
    var style = document.createElement('style')
    style.id = 'yto-notify-style'
    style.type = 'text/css'
    style.textContent = CSS_TEXT
    document.head.appendChild(style)
  }

  // ======================== 工具函数 ========================
  function el (tag, cls, attrs) {
    var node = document.createElement(tag)
    if (cls) node.className = cls
    if (attrs) for (var k in attrs) {
      if (k === 'text') node.textContent = attrs[k]
      else if (k === 'html') node.innerHTML = attrs[k]
      else node.setAttribute(k, attrs[k])
    }
    return node
  }

  // 获取当前时间字符串 yyyy-MM-dd HH:mm:ss
  function getNowFormat () {
    var d = new Date()
    var pad = function (n, len) { var s = '' + n; while (s.length < (len || 2)) s = '0' + s; return s }
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
      + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds())
  }

  // 解析颜色为 [r, g, b]，支持 #rgb / #rrggbb / rgb(r,g,b)
  function parseColor (str) {
    if (!str) return null
    str = str.trim()
    if (str[0] === '#') {
      var hex = str.slice(1)
      if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2]
      if (hex.length !== 6) return null
      return [parseInt(hex.slice(0,2),16), parseInt(hex.slice(2,4),16), parseInt(hex.slice(4,6),16)]
    }
    var m = str.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
    if (m) return [+m[1], +m[2], +m[3]]
    return null
  }

  // 将颜色向白色方向混合，amount: 0~1（0=原色，1=白色）
  function lighten (rgb, amount) {
    var r = Math.round(rgb[0] + (255 - rgb[0]) * amount)
    var g = Math.round(rgb[1] + (255 - rgb[1]) * amount)
    var b = Math.round(rgb[2] + (255 - rgb[2]) * amount)
    return 'rgb(' + r + ',' + g + ',' + b + ')'
  }

  // 从 config 解析主题色三阶
  function resolveTheme (config) {
    var rgb = parseColor(config.themeColor)
    return {
      primary:  rgb ? lighten(rgb, 0)    : '#9547ec',
      light:    rgb ? lighten(rgb, 0.25)  : '#b075f1',
      lighter:  rgb ? lighten(rgb, 0.5)   : '#caa3f6'
    }
  }

  // ======================== 环境检测 ========================

  /**
   * 检测当前是否在 Electron 渲染进程中
   */
  function isElectron () {
    if (typeof window !== 'undefined' && window.process && window.process.type === 'renderer') return true
    if (typeof navigator !== 'undefined' && /Electron/i.test(navigator.userAgent)) return true
    return false
  }

  /**
   * 检测当前是否在 NW.js 环境中
   */
  function isNWjs () {
    return typeof window !== 'undefined' && typeof window.nw !== 'undefined'
  }

  /**
   * 在外部浏览器中打开链接（兼容 Web / Electron / NW.js）
   * - Electron: 使用 electron.shell.openExternal
   * - NW.js:    使用 nw.Shell.openExternal
   * - Web:      使用 <a> 标签 target=_blank
   */
  function openExternal (url) {
    if (isElectron()) {
      try {
        var shell = (window.require || require)('electron').shell
        shell.openExternal(url)
        return
      } catch (e) { /* fallback */ }
    }
    if (isNWjs()) {
      try {
        window.nw.Shell.openExternal(url)
        return
      } catch (e) { /* fallback */ }
    }
    // Web 浏览器回退
    var a = document.createElement('a')
    a.href = url
    a.target = '_blank'
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // ======================== 系统信息检测 ========================

  /**
   * 同步检测：系统平台名称 + 操作系统版本号
   * 返回 { platform: 'Windows', version: '10.0.19042' }
   */
  function getSystemInfo () {
    var ua = (typeof navigator !== 'undefined' && navigator.userAgent) ? navigator.userAgent : ''
    var platform = ''
    var version = ''

    // ---- 平台 ----
    if (/Windows/i.test(ua)) platform = 'Windows'
    else if (/Macintosh|Mac OS X/i.test(ua)) platform = 'macOS'
    else if (/Linux/i.test(ua)) platform = 'Linux'
    else if (/Android/i.test(ua)) platform = 'Android'
    else if (/iPhone|iPad|iPod/i.test(ua)) platform = 'iOS'
    else platform = (typeof navigator !== 'undefined' && navigator.platform) || ''

    // ---- 操作系统版本号 ----
    if (/Windows NT ([\d.]+)/i.test(ua)) {
      version = RegExp.$1
    } else if (/Mac OS X ([\d_.]+)/i.test(ua)) {
      version = RegExp.$1.replace(/_/g, '.')
    } else if (/Android ([\d.]+)/i.test(ua)) {
      version = RegExp.$1
    } else if (/Linux.*\(([^)]+)\)/i.test(ua)) {
      version = RegExp.$1
    }

    // Electron / NW.js 下使用 os.release() 补充（可拿到 Windows build 号，如 10.0.19042）
    if (!version && typeof require === 'function') {
      try {
        var os = require('os')
        version = os.release() || ''
      } catch (e) { /* ignore */ }
    }

    // 若 UA 只拿到主版本号（如 "10.0"），尝试用 os.release() 获取完整 build（如 "10.0.19042"）
    if (version && version.split('.').length <= 2 && typeof require === 'function') {
      try {
        var os2 = require('os')
        var rel = os2.release()
        if (rel && rel.split('.').length > 2) version = rel
      } catch (e) { /* ignore */ }
    }

    return { platform: platform, version: version }
  }

  // 模块加载时同步缓存 platform / version
  var _cachedSysInfo = getSystemInfo()

  // ---- 设备品牌 / 型号 / 应用版本 异步检测 ----
  // PC 客户端 (Electron / NW.js)：通过 child_process + Electron/NW.js API 获取
  // Web 浏览器：通过 navigator.userAgentData.getHighEntropyValues 获取
  var _deviceInfo = { brand: '', type: '', version: '' }
  var _deviceInfoPromise = null

  function detectDeviceInfo () {
    if (_deviceInfoPromise) return _deviceInfoPromise

    _deviceInfoPromise = new Promise(function (resolve) {
      var done = function () { resolve(_deviceInfo) }

      // ---- PC 客户端 ----
      if (isElectron() || isNWjs()) {
        // -- 应用版本 --
        try {
          if (isElectron()) {
            // Electron: remote.app.getVersion()（主进程/渲染进程均可）
            try {
              var remote = (window.require || require)('electron').remote
              _deviceInfo.version = remote.app.getVersion() || ''
            } catch (e1) {
              try {
                // @electron/remote 新版写法
                var remote2 = (window.require || require)('@electron/remote')
                _deviceInfo.version = remote2.app.getVersion() || ''
              } catch (e2) { /* ignore */ }
            }
          } else if (isNWjs()) {
            // NW.js: manifest 中的 version
            _deviceInfo.version = (window.nw.App.manifest && window.nw.App.manifest.version) || ''
          }
        } catch (e) { /* ignore */ }

        // 兜底：从 UA 中提取 "App/x.x.x" 格式
        if (!_deviceInfo.version) {
          var uaAppVer = navigator.userAgent.match(/\s([\w-]+)\/([\d]+\.[\d]+(?:\.[\d]+)*)/)
          if (uaAppVer) _deviceInfo.version = uaAppVer[2]
        }

        // -- 设备品牌 / 型号 --
        try {
          var execSync = require('child_process').execSync
          if (_cachedSysInfo.platform === 'Windows') {
            var out = execSync(
              'wmic computersystem get manufacturer,model /format:list',
              { encoding: 'utf8', timeout: 3000, windowsHide: true }
            )
            var mfr = out.match(/Manufacturer=(.+)/i)
            var mdl = out.match(/Model=(.+)/i)
            _deviceInfo.brand = mfr ? mfr[1].trim() : ''
            _deviceInfo.type = mdl ? mdl[1].trim() : ''
          } else if (_cachedSysInfo.platform === 'macOS') {
            var brandOut = execSync(
              'sysctl -n hw.model',
              { encoding: 'utf8', timeout: 3000 }
            )
            _deviceInfo.brand = 'Apple'
            _deviceInfo.type = (brandOut || '').trim()
          }
          return done()
        } catch (e) { return done() }
      }

      // ---- Web 浏览器：User-Agent Client Hints (Chrome 90+ / Edge 90+) ----
      if (typeof navigator !== 'undefined' && navigator.userAgentData &&
          typeof navigator.userAgentData.getHighEntropyValues === 'function') {
        navigator.userAgentData.getHighEntropyValues(['brand', 'model'])
          .then(function (uaData) {
            _deviceInfo.brand = uaData.brand || ''
            _deviceInfo.type = uaData.model || ''
            done()
          })
          .catch(function () { done() })
        return
      }

      done()
    })

    return _deviceInfoPromise
  }

  // ====================================================================
  //  Handler 注册表：key = function 编号，value = Handler 构造函数
  //  每个 Handler 需实现：
  //    constructor(config)     — config 含 { theme, onBeforeOpen, onAfterClose, reportConfig }
  //    render(itemList)        — itemList 为接口返回的 result 数组
  //    destroy()               — 清理 DOM 和定时器
  // ====================================================================
  var _handlers = {}

  // ====================================================================
  //  function=30  图片通知弹框 Handler
  // ====================================================================
  function ImagePopupHandler (config) {
    this._theme = config.theme
    this._onBeforeOpen = config.onBeforeOpen || null
    this._onAfterClose = config.onAfterClose || null
    this._reportConfig = config.reportConfig || null

    // DOM
    this._overlay = null
    this._closeBtn = null
    this._slides = []
    this._dots = []

    // 状态
    this._currentIndex = 0
    this._carouselTimer = null
    this._carouselInterval = 3000
    this._paused = false
    this._realCount = 0
    this._countdown = 0
    this._countdownTimer = null

    // 队列：多条通知逐条弹框
    this._queue = null
    this._queueIndex = 0
    this._queueManager = null

    // 上报
    this._reportData = null
    this._frequency = ''
    this._resultConfirmed = 0
    this._browseRequired = 0
    this._reported = false
    this._reachAchieved = false
    this._browseStart = 0
    this._browseAccumulated = 0
    this._browseTimer = null

    this._handleVisibilityChange = this._onVisibilityChange.bind(this)
  }

  // ----- render -----
  // itemList: 接口返回的 result 数组，多条数据逐条弹框展示
  ImagePopupHandler.prototype.render = function (itemList) {
    var self = this
    if (!itemList || !itemList.length) return

    // 首次调用（多条）：存入队列，逐条弹框
    if (itemList.length > 1 && !this._queue) {
      this._queue = itemList
      this._queueIndex = 0
    }

    var item = this._queue ? this._queue[this._queueIndex] : itemList[0]
    if (!item) return
    var detail = item.detail || {}
    var attachmentList = detail.attachment_list || []
    if (!attachmentList.length) return

    if (this._onBeforeOpen) this._onBeforeOpen(detail)

    // 上报数据
    this._reportData = {
      msgPublishId: item.id,
      functionType: item.function || 30,
      mpUpdateTime: item.update_time || ''
    }
    // frequency_unit: 4=单次 0=每次 1/2/3/5=周期
    var FREQ_MAP = { 4: '单次', 0: '每次', 1: '周期', 2: '周期', 3: '周期', 5: '周期' }
    this._frequency = FREQ_MAP[detail.frequency_unit] || ''
    // result_confirmed: 0=曝光 1=点击 2=获取结果 3=有效触达
    this._resultConfirmed = detail.result_confirmed != null ? detail.result_confirmed : 0
    this._reported = false
    this._reachAchieved = false
    this._browseRequired = (this._resultConfirmed === 3) ? (detail.ie_time || 0) : 0

    // 解析配置
    var popSettings = detail.pop_settings
    var minVal = detail.min_value || 60
    var maxVal = detail.max_value || 45
    var dialogW = popSettings === 2 ? minVal + 'px' : minVal + '%'
    var dialogH = popSettings === 2 ? maxVal + 'px' : maxVal + '%'
    var interval = (detail.interval || 3) * 1000
    var forceRead = detail.force_read === 1
    var effectDuration = detail.effect_duration || 3

    // 遮罩 + 主题色变量
    var overlay = el('div', 'yto-notify-overlay')
    overlay.style.setProperty('--yto-primary', this._theme.primary)
    overlay.style.setProperty('--yto-primary-light', this._theme.light)
    overlay.style.setProperty('--yto-primary-lighter', this._theme.lighter)
    this._overlay = overlay

    // 弹框
    var dialog = el('div', 'yto-notify-dialog')
    dialog.style.width = dialogW
    dialog.style.height = dialogH

    // 轮播区域
    var body = el('div', 'yto-notify-body')
    var carousel = el('div', 'yto-carousel')
    // pause-on-hover：悬停暂停 + 箭头出现，移开恢复 + 箭头消失
    carousel.addEventListener('mouseenter', function () { self._pauseAutoPlay() })
    carousel.addEventListener('mouseleave', function () { self._resumeAutoPlay() })
    this._slides = []
    this._dots = []

    // 2 张图时翻倍（AB→ABAB），让轮播始终同向过渡
    this._realCount = attachmentList.length
    if (attachmentList.length === 2) {
      attachmentList = attachmentList.concat(attachmentList)
    }

    for (var i = 0; i < attachmentList.length; i++) {
      var group = attachmentList[i]
      var itemData = (group && group[0]) || {}
      var imgUrl = itemData.full_url || ''
      var extraInfo = itemData.extra_info || {}
      var jumpType = extraInfo.jumpType != null ? extraInfo.jumpType : 0
      var mountLink = extraInfo.mountLink || ''
      var slide = el('div', 'yto-slide' + (i === 0 ? ' yto-active' : ''))
      var img = el('img', '', { src: imgUrl, alt: '通知图片' + (i + 1) })
      img.onerror = function () { this.alt = '图片加载失败'; this.src = '' }
      if (mountLink) {
        img.style.cursor = 'pointer'
        img.addEventListener('click', (function (link, type) {
          return function () { self._onMountLinkClick(link, type) }
        })(mountLink, jumpType))
      }
      slide.appendChild(img)
      carousel.appendChild(slide)
      this._slides.push(slide)
    }

    if (this._realCount > 1) {
      var svgLeft = '<svg viewBox="0 0 14 14"><polyline points="9 2 4 7 9 12"/></svg>'
      var svgRight = '<svg viewBox="0 0 14 14"><polyline points="5 2 10 7 5 12"/></svg>'
      var arrowL = el('button', 'yto-arrow yto-arrow-left', { html: svgLeft })
      var arrowR = el('button', 'yto-arrow yto-arrow-right', { html: svgRight })
      arrowL.addEventListener('click', function () { self._prev() })
      arrowR.addEventListener('click', function () { self._next() })
      carousel.appendChild(arrowL)
      carousel.appendChild(arrowR)

      // 指示器按原始数量创建，点击时映射到翻倍后的索引
      var dotsWrap = el('div', 'yto-indicators')
      var realLen = this._realCount
      var totalLen = attachmentList.length
      for (var j = 0; j < realLen; j++) {
        ;(function (idx) {
          var dot = el('button', 'yto-dot' + (idx === 0 ? ' yto-dot-active' : ''))
          dot.addEventListener('click', function () {
            var targetIdx = idx
            if (totalLen > realLen) {
              if (self._currentIndex >= realLen) targetIdx = idx + realLen
            }
            self._goTo(targetIdx)
          })
          dotsWrap.appendChild(dot)
          self._dots.push(dot)
        })(j)
      }
    }

    body.appendChild(carousel)
    dialog.appendChild(body)

    // 底部操作区：指示器 + 关闭按钮
    var footer = el('div', 'yto-notify-footer')
    if (this._dots.length) {
      footer.appendChild(dotsWrap)
    }
    var closeBtn = el('button', 'yto-notify-close-btn')
    if (forceRead) {
      closeBtn.classList.add('yto-disabled')
      closeBtn.textContent = effectDuration + 's 后可关闭'
    } else {
      closeBtn.textContent = '关闭'
    }
    closeBtn.addEventListener('click', function () { self._close() })
    this._closeBtn = closeBtn
    footer.appendChild(closeBtn)

    // 组装：wrapper 包裹 dialog + footer（footer 在弹框外部）
    var wrapper = el('div', 'yto-notify-wrapper')
    wrapper.appendChild(dialog)
    wrapper.appendChild(footer)
    overlay.appendChild(wrapper)
    document.body.appendChild(overlay)

    // 自动轮播
    this._currentIndex = 0
    this._carouselInterval = interval
    this._startAutoPlay(interval, attachmentList.length)

    // 强制阅读倒计时
    if (forceRead) {
      this._countdown = effectDuration
      this._startCountdown(effectDuration)
    }

    // ---- 触达上报 ----
    if (this._reportConfig && this._reportData) {
      // 有效触达：启动浏览时长计时 + visibilitychange 监听
      if (this._resultConfirmed === 3) {
        this._startBrowseTrack()
        document.addEventListener('visibilitychange', this._handleVisibilityChange)
      }
      // 根据 frequency / result_confirmed 决定是否立即上报
      this._reportReach()
    }
  }

  // ----- 轮播 -----
  ImagePopupHandler.prototype._startAutoPlay = function (interval, total) {
    var self = this
    this._stopAutoPlay()
    if (total <= 1 || interval <= 0) return
    this._paused = false
    this._carouselTimer = setInterval(function () {
      var next = (self._currentIndex + 1) % total
      self._goTo(next)
    }, interval)
  }
  ImagePopupHandler.prototype._stopAutoPlay = function () {
    if (this._carouselTimer) { clearInterval(this._carouselTimer); this._carouselTimer = null }
    this._paused = false
  }
  // hover → clearInterval，标记暂停
  ImagePopupHandler.prototype._pauseAutoPlay = function () {
    if (this._paused || !this._carouselTimer) return
    this._paused = true
    clearInterval(this._carouselTimer)
    this._carouselTimer = null
  }
  // 移开 → 从完整间隔重新计时（el-carousel 行为）
  ImagePopupHandler.prototype._resumeAutoPlay = function () {
    if (!this._paused || !this._slides.length) return
    this._startAutoPlay(this._carouselInterval, this._slides.length)
  }
  ImagePopupHandler.prototype._prev = function () {
    var total = this._slides.length
    var prev = (this._currentIndex - 1 + total) % total
    this._goTo(prev); this._restartAutoPlay()
  }
  ImagePopupHandler.prototype._next = function () {
    var total = this._slides.length
    var next = (this._currentIndex + 1) % total
    this._goTo(next); this._restartAutoPlay()
  }
  ImagePopupHandler.prototype._goTo = function (index) {
    if (index < 0 || index >= this._slides.length) return
    if (index === this._currentIndex) return
    var total = this._slides.length
    var current = this._currentIndex
    var curSlide = this._slides[current]
    var nextSlide = this._slides[index]

    // 判断方向：正向(next) / 反向(prev)，含循环边界
    var forward = index > current
    // 循环边界修正：最后一张→第一张 = 正向，第一张→最后一张 = 反向
    if (index === 0 && current === total - 1) forward = true
    if (index === total - 1 && current === 0) forward = false

    // 清理所有非当前、非目标的 slide 状态
    for (var i = 0; i < total; i++) {
      if (i !== current && i !== index) {
        this._slides[i].classList.add('yto-no-transition')
        this._slides[i].classList.remove('yto-active', 'yto-slide-left')
        this._slides[i].offsetHeight // force reflow
        this._slides[i].classList.remove('yto-no-transition')
      }
    }

    if (forward) {
      // 当前 slide 向左退出 → translateX(-100%)
      curSlide.classList.remove('yto-active')
      curSlide.classList.add('yto-slide-left')
      // 目标 slide 从右侧进入：先定位到右侧（无动画），再滑到中间
      nextSlide.classList.add('yto-no-transition')
      nextSlide.classList.remove('yto-slide-left', 'yto-active')
      nextSlide.offsetHeight // force reflow
      nextSlide.classList.remove('yto-no-transition')
      nextSlide.classList.add('yto-active')
    } else {
      // 当前 slide 向右退出 → 默认 translateX(100%)
      curSlide.classList.remove('yto-active')
      // 目标 slide 从左侧进入：先定位到左侧（无动画），再滑到中间
      nextSlide.classList.add('yto-no-transition')
      nextSlide.classList.add('yto-slide-left')
      nextSlide.classList.remove('yto-active')
      nextSlide.offsetHeight // force reflow
      nextSlide.classList.remove('yto-no-transition', 'yto-slide-left')
      nextSlide.classList.add('yto-active')
    }

    // 同步指示器（取模映射回原始索引）
    if (this._dots.length > 0) {
      var realCount = this._realCount || total
      var curDot = current % realCount
      var nextDot = index % realCount
      if (curDot !== nextDot) {
        this._dots[curDot].classList.remove('yto-dot-active')
        this._dots[nextDot].classList.add('yto-dot-active')
      }
    }
    this._currentIndex = index
  }
  ImagePopupHandler.prototype._restartAutoPlay = function () {
    if (!this._overlay) return
    this._startAutoPlay(this._carouselInterval, this._slides.length)
  }

  // ----- 倒计时 -----
  ImagePopupHandler.prototype._startCountdown = function (duration) {
    var self = this
    this._clearCountdown()
    this._countdown = duration
    this._countdownTimer = setInterval(function () {
      self._countdown--
      if (self._countdown <= 0) {
        self._clearCountdown()
        if (self._closeBtn) { self._closeBtn.classList.remove('yto-disabled'); self._closeBtn.textContent = '关闭' }
      } else {
        if (self._closeBtn) self._closeBtn.textContent = self._countdown + 's 后可关闭'
      }
    }, 1000)
  }
  ImagePopupHandler.prototype._clearCountdown = function () {
    if (this._countdownTimer) { clearInterval(this._countdownTimer); this._countdownTimer = null }
  }

  // ----- 关闭 & 销毁 -----
  ImagePopupHandler.prototype._close = function () {
    if (this._countdown > 0) return

    // 关闭时按触达标准上报
    if (this._reportConfig && this._reportData && !this._reported) {
      if (this._resultConfirmed === 1) {
        // 点击：关闭即上报 event=1
        this._report('1')
      } else if (this._resultConfirmed === 3) {
        // 有效触达：达到浏览时长 → event=3，未达到 → event=1
        this._report(this._reachAchieved ? '3' : '1')
      }
      // result_confirmed=0（曝光）已在展示时上报，result_confirmed=2（获取结果）暂不处理
    }

    // 销毁当前弹框 DOM
    this.destroy()

    // 跨场景队列：由 queueManager 统一调度下一条
    if (this._queueManager) {
      this._queueManager.advance()
      return
    }

    // 同场景队列：还有下一条 → 自动弹出
    if (this._queue && this._queueIndex < this._queue.length - 1) {
      this._queueIndex++
      this.render([this._queue[this._queueIndex]])
    } else {
      // 全部展示完毕，回调通知调用方
      if (this._onAfterClose) this._onAfterClose()
    }
  }

  // ----- 上报 -----

  /**
   * 根据 frequency / result_confirmed 决定是否在展示时立即上报
   */
  ImagePopupHandler.prototype._reportReach = function () {
    // 每次弹框打开都上报 event=0（不依赖 _reported 标记）
    this._report('0')
  }

  /**
   * 图片跳转链接点击：上报 event=3 并按 jumpType 打开链接
   * @param {string} url — 跳转地址
   * @param {number} jumpType — 1=当前页跳转  2=新建页面跳转（兼容 Electron / NW.js）
   */
  ImagePopupHandler.prototype._onMountLinkClick = function (url, jumpType) {
    if (url) {
      // 有链接：上报 event=3 + 跳转
      if (!this._reported && this._reportConfig && this._reportData) {
        this._report('3')
      }

      if (jumpType === 1) {
        window.location.href = url
      } else {
        openExternal(url)
      }
    }
    // 无链接：不做处理
  }

  /**
   * 浏览时长计时 tick（每秒）
   * 仅 result_confirmed=3（有效触达）时使用
   */
  ImagePopupHandler.prototype._tickBrowseTime = function () {
    var dur = this._getBrowseDuration()
    if (this._browseRequired > 0 && dur >= this._browseRequired) {
      this._reachAchieved = true
      // 达到浏览时长，仅标记；由关闭按钮触发 event=3
    }
  }

  /**
   * 获取当前累计浏览秒数（只读，不修改状态）
   */
  ImagePopupHandler.prototype._getBrowseDuration = function () {
    var extra = 0
    if (this._browseStart > 0) {
      extra = Math.round((Date.now() - this._browseStart) / 1000)
    }
    return this._browseAccumulated + extra
  }

  ImagePopupHandler.prototype._startBrowseTrack = function () {
    this._pauseBrowseTrack()
    this._browseStart = Date.now()
    this._browseAccumulated = 0
    var self = this
    this._browseTimer = setInterval(function () { self._tickBrowseTime() }, 1000)
  }

  ImagePopupHandler.prototype._pauseBrowseTrack = function () {
    if (this._browseStart > 0) {
      this._browseAccumulated += Math.round((Date.now() - this._browseStart) / 1000)
      this._browseStart = 0
    }
    if (this._browseTimer) { clearInterval(this._browseTimer); this._browseTimer = null }
  }

  ImagePopupHandler.prototype._resumeBrowseTrack = function () {
    if (!this._overlay || this._reported) return
    this._browseStart = Date.now()
    var self = this
    this._browseTimer = setInterval(function () { self._tickBrowseTime() }, 1000)
  }

  ImagePopupHandler.prototype._onVisibilityChange = function () {
    if (!this._overlay) return
    if (document.hidden) {
      this._pauseBrowseTrack()
    } else {
      this._resumeBrowseTrack()
    }
  }

  /**
   * 核心上报入口：先确保设备信息检测完成，再发送
   * @param {string} eventCode — "0"=曝光  "1"=点击关闭  "3"=有效触达/链接跳转
   * @param {number} [duration] — 浏览秒数
   */
  ImagePopupHandler.prototype._report = function (eventCode, duration) {
    if (!this._reportConfig || !this._reportData) return
    if (this._reported && eventCode !== '0') return // 非 event=0 防重复上报

    if (eventCode !== '0') {
      this._reported = true
      this._pauseBrowseTrack()
    }

    var self = this
    var browseDuration = typeof duration === 'number' ? duration : this._getBrowseDuration()

    // 触发设备信息检测（首次调用后缓存），等待完成后发送
    detectDeviceInfo().then(function () {
      self._sendReport(eventCode, browseDuration)
    })
  }

  /**
   * 实际发送上报（在设备信息检测完成后调用）
   */
  ImagePopupHandler.prototype._sendReport = function (eventCode, browseDuration) {
    var payload = {
      msg_publish_id: this._reportData.msgPublishId,
      function: this._reportData.functionType,
      user_code: this._reportConfig.usercode,
      event: eventCode,
      duration: browseDuration,
      app_version: _deviceInfo.version || '',
      system_platform: _cachedSysInfo.platform,
      device_brand: _deviceInfo.brand || '',
      device_type: _deviceInfo.type || '',
      system_version: _cachedSysInfo.version,
      system_code: this._reportConfig.system || '',
      // real_result: '',
      update_time: this._reportData.mpUpdateTime
    }

    // 可选扩展参数（由调用方 init 时传入）
    var extra = this._reportConfig.extraParams || {}
    for (var k in extra) {
      if (extra.hasOwnProperty(k) && !payload.hasOwnProperty(k)) {
        payload[k] = extra[k]
      }
    }

    var url = this._reportConfig.reportUrl

    var xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('TOKEN', TOKEN)
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var res = JSON.parse(xhr.responseText)
          if (res.code === 200) {
            console.log('[YtoNotify] 上报成功 event=' + eventCode, payload)
          } else {
            console.warn('[YtoNotify] 上报返回异常:', res.msg)
          }
        } catch (e) { /* ignore parse error */ }
      } else {
        console.warn('[YtoNotify] 上报失败 HTTP ' + xhr.status)
      }
    }
    xhr.onerror = function () { console.warn('[YtoNotify] 上报网络错误') }
    xhr.send(JSON.stringify(payload))
  }

  ImagePopupHandler.prototype.destroy = function () {
    this._stopAutoPlay()
    this._clearCountdown()
    this._pauseBrowseTrack()
    document.removeEventListener('visibilitychange', this._handleVisibilityChange)
    if (this._overlay && this._overlay.parentNode) {
      this._overlay.parentNode.removeChild(this._overlay)
    }
    this._overlay = null
    this._closeBtn = null
    this._slides = []
    this._dots = []
    this._currentIndex = 0
  }

  // 注册图片通知 Handler（function=30）
  _handlers[30] = ImagePopupHandler

  // ====================================================================
  //  function=31  图文公告 Handler
  // ====================================================================
  function ArticleNoticeHandler (config) {
    this._theme = config.theme
    this._onBeforeOpen = config.onBeforeOpen || null
    this._onAfterClose = config.onAfterClose || null
    this._reportConfig = config.reportConfig || null

    // DOM
    this._overlay = null
    this._closeBtn = null
    this._countdownEl = null
    this._countdownSecondEl = null
    this._actionBtns = null

    // 队列
    this._queue = null
    this._queueIndex = 0
    this._queueManager = null

    // 状态
    this._countdown = 0
    this._countdownTimer = null

    // 上报
    this._reportData = null
    this._frequency = ''
    this._resultConfirmed = 0
    this._browseRequired = 0
    this._reported = false
    this._reachAchieved = false
    this._browseStart = 0
    this._browseAccumulated = 0
    this._browseTimer = null

    this._handleVisibilityChange = this._onVisibilityChange.bind(this)
  }

  // ----- render -----
  ArticleNoticeHandler.prototype.render = function (itemList) {
    var self = this
    if (!itemList || !itemList.length) return

    // 队列初始化（首次调用且有多条数据时）
    if (itemList.length > 1 && !this._queue) {
      this._queue = itemList
      this._queueIndex = 0
    }

    var item = this._queue ? this._queue[this._queueIndex] : itemList[0]
    if (!item) return
    var detail = item.detail || {}

    if (this._onBeforeOpen) this._onBeforeOpen(detail)

    // 上报数据
    this._reportData = {
      msgPublishId: item.id,
      functionType: item.function || 31,
      mpUpdateTime: getNowFormat()
    }
    var FREQ_MAP = { 4: '单次', 0: '每次', 1: '周期', 2: '周期', 3: '周期', 5: '周期' }
    var freqUnit = item.frequency_unit != null ? item.frequency_unit : detail.frequency_unit
    this._frequency = FREQ_MAP[freqUnit] || ''
    var rc = item.result_confirmed != null ? item.result_confirmed : detail.result_confirmed
    this._resultConfirmed = rc != null ? rc : 0
    this._reported = false
    this._reachAchieved = false
    this._browseRequired = (this._resultConfirmed === 3) ? (detail.ie_time || 0) : 0

    // 解析配置
    var popSettings = detail.pop_settings
    var minVal = detail.min_value || 60
    var maxVal = detail.max_value || 45
    var dialogW = popSettings === 2 ? minVal + 'px' : minVal + '%'
    var dialogH = popSettings === 2 ? maxVal + 'px' : maxVal + '%'
    var forceRead = detail.force_read === 1
    var effectDuration = detail.effect_duration || 3

    // 遮罩 + 主题色变量
    var overlay = el('div', 'yto-article-overlay')
    overlay.style.setProperty('--yto-primary', this._theme.primary)
    overlay.style.setProperty('--yto-primary-light', this._theme.light)
    overlay.style.setProperty('--yto-primary-lighter', this._theme.lighter)
    this._overlay = overlay

    // 弹框
    var dialog = el('div', 'yto-article-dialog')
    dialog.style.width = dialogW
    dialog.style.height = dialogH

    // 富文本内容
    var body = el('div', 'yto-article-body')
    var contentWrap = el('div', 'yto-article-content')
    var content = detail.content || ''
    if (content) {
      contentWrap.innerHTML = content
    }
    body.appendChild(contentWrap)
    dialog.appendChild(body)

    // 底部：倒计时 + 按钮
    var footer = el('div', 'yto-article-footer')

    // 倒计时显示（强制阅读时显示）
    var countdownEl = null
    var countdownSecondEl = null
    if (forceRead && effectDuration > 0) {
      countdownEl = el('div', 'yto-article-countdown')
      countdownSecondEl = el('span', 'yto-article-countdown-second', { text: effectDuration })
      countdownEl.appendChild(countdownSecondEl)
      countdownEl.appendChild(document.createTextNode(' 秒后可关闭'))
      footer.appendChild(countdownEl)
    }
    this._countdownEl = countdownEl
    this._countdownSecondEl = countdownSecondEl

    // 按钮区域
    var btnsWrap = el('div', 'yto-article-btns')

    // 关闭按钮（倒计时期间隐藏，倒计时结束后显示）
    var closeBtn = el('button', 'yto-article-btn yto-article-close-btn', { text: '关闭' })
    if (forceRead) {
      closeBtn.style.display = 'none'
    }
    closeBtn.addEventListener('click', function () { self._close() })
    this._closeBtn = closeBtn
    btnsWrap.appendChild(closeBtn)

    // 动态按钮（attach_info，倒序排列：从右到左）
    var attachInfo = detail.attach_info || []
    this._actionBtns = []
    for (var i = attachInfo.length - 1; i >= 0; i--) {
      ;(function (btn) {
        var btnEl = el('button', 'yto-article-btn', { text: btn.btn_content || '按钮' })
        if (forceRead) {
          btnEl.classList.add('yto-disabled')
        }
        var jt = btn.jumpType != null ? btn.jumpType : 0
        var ml = btn.mountLink || ''
        btnEl.addEventListener('click', function () {
          self._onBtnLinkClick(ml, jt)
        })
        btnsWrap.appendChild(btnEl)
        self._actionBtns.push(btnEl)
      })(attachInfo[i])
    }

    footer.appendChild(btnsWrap)
    dialog.appendChild(footer)

    // 组装
    overlay.appendChild(dialog)
    document.body.appendChild(overlay)

    // 强制阅读倒计时
    if (forceRead) {
      this._countdown = effectDuration
      this._startCountdown(effectDuration)
    }

    // ---- 触达上报 ----
    if (this._reportConfig && this._reportData) {
      if (this._resultConfirmed === 3) {
        this._startBrowseTrack()
        document.addEventListener('visibilitychange', this._handleVisibilityChange)
      }
      this._reportReach()
    }
  }

  // ----- 倒计时 -----
  ArticleNoticeHandler.prototype._startCountdown = function (duration) {
    var self = this
    this._clearCountdown()
    this._countdown = duration
    this._countdownTimer = setInterval(function () {
      self._countdown--
      if (self._countdownSecondEl) self._countdownSecondEl.textContent = self._countdown
      if (self._countdown <= 0) {
        self._clearCountdown()
        // 隐藏倒计时
        if (self._countdownEl) self._countdownEl.style.display = 'none'
        // 显示关闭按钮
        if (self._closeBtn) self._closeBtn.style.display = ''
        // 启用动态按钮
        if (self._actionBtns) {
          for (var i = 0; i < self._actionBtns.length; i++) {
            self._actionBtns[i].classList.remove('yto-disabled')
          }
        }
      }
    }, 1000)
  }
  ArticleNoticeHandler.prototype._clearCountdown = function () {
    if (this._countdownTimer) { clearInterval(this._countdownTimer); this._countdownTimer = null }
  }

  // ----- 关闭 & 销毁 -----
  ArticleNoticeHandler.prototype._close = function () {
    if (this._countdown > 0) return

    // 关闭时按触达标准上报
    if (this._reportConfig && this._reportData && !this._reported) {
      if (this._resultConfirmed === 1) {
        this._report('1')
      } else if (this._resultConfirmed === 3) {
        // 有效触达：达到浏览时长 → event=3，未达到 → event=1
        this._report(this._reachAchieved ? '3' : '1')
      }
    }

    this.destroy()

    // 跨场景队列：由 queueManager 统一调度下一条
    if (this._queueManager) {
      this._queueManager.advance()
      return
    }

    // 同场景队列：还有下一条 → 自动弹出
    if (this._queue && this._queueIndex < this._queue.length - 1) {
      this._queueIndex++
      this.render([this._queue[this._queueIndex]])
    } else {
      if (this._onAfterClose) this._onAfterClose()
    }
  }

  // ----- 按钮跳转 -----
  ArticleNoticeHandler.prototype._onBtnLinkClick = function (url, jumpType) {
    if (url) {
      // 有链接：上报 event=3 + 跳转
      if (!this._reported && this._reportConfig && this._reportData) {
        this._report('3')
      }

      if (jumpType === 1) {
        window.location.href = url
      } else {
        openExternal(url)
      }
    } else {
      // 无链接：同右上角关闭按钮
      this._close()
    }
  }

  // ----- 上报 -----
  ArticleNoticeHandler.prototype._reportReach = function () {
    // 每次弹框打开都上报 event=0（不依赖 _reported 标记）
    this._report('0')
  }

  ArticleNoticeHandler.prototype._report = function (eventCode, duration) {
    if (!this._reportConfig || !this._reportData) return
    if (this._reported && eventCode !== '0') return

    if (eventCode !== '0') {
      this._reported = true
      this._pauseBrowseTrack()
    }

    var self = this
    var browseDuration = typeof duration === 'number' ? duration : this._getBrowseDuration()

    detectDeviceInfo().then(function () {
      self._sendReport(eventCode, browseDuration)
    })
  }

  ArticleNoticeHandler.prototype._sendReport = function (eventCode, browseDuration) {
    var payload = {
      msg_publish_id: this._reportData.msgPublishId,
      'function': this._reportData.functionType,
      user_code: this._reportConfig.usercode,
      event: eventCode,
      duration: browseDuration,
      app_version: _deviceInfo.version || '',
      system_platform: _cachedSysInfo.platform,
      device_brand: _deviceInfo.brand || '',
      device_type: _deviceInfo.type || '',
      system_version: _cachedSysInfo.version,
      system_code: this._reportConfig.system || ''
    }

    var extra = this._reportConfig.extraParams || {}
    for (var k in extra) {
      if (extra.hasOwnProperty(k) && !payload.hasOwnProperty(k)) {
        payload[k] = extra[k]
      }
    }

    var url = this._reportConfig.reportUrl

    var xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('TOKEN', TOKEN)
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var res = JSON.parse(xhr.responseText)
          if (res.code === 200) {
            console.log('[YtoNotify] 上报成功 event=' + eventCode, payload)
          } else {
            console.warn('[YtoNotify] 上报返回异常:', res.msg)
          }
        } catch (e) { /* ignore */ }
      } else {
        console.warn('[YtoNotify] 上报失败 HTTP ' + xhr.status)
      }
    }
    xhr.onerror = function () { console.warn('[YtoNotify] 上报网络错误') }
    xhr.send(JSON.stringify(payload))
  }

  // ----- 浏览时长追踪 -----
  ArticleNoticeHandler.prototype._tickBrowseTime = function () {
    var dur = this._getBrowseDuration()
    if (this._browseRequired > 0 && dur >= this._browseRequired) {
      this._reachAchieved = true
      // 达到浏览时长，仅标记；由关闭按钮触发 event=3
    }
  }
  ArticleNoticeHandler.prototype._getBrowseDuration = function () {
    var extra = 0
    if (this._browseStart > 0) {
      extra = Math.round((Date.now() - this._browseStart) / 1000)
    }
    return this._browseAccumulated + extra
  }
  ArticleNoticeHandler.prototype._startBrowseTrack = function () {
    this._pauseBrowseTrack()
    this._browseStart = Date.now()
    this._browseAccumulated = 0
    var self = this
    this._browseTimer = setInterval(function () { self._tickBrowseTime() }, 1000)
  }
  ArticleNoticeHandler.prototype._pauseBrowseTrack = function () {
    if (this._browseStart > 0) {
      this._browseAccumulated += Math.round((Date.now() - this._browseStart) / 1000)
      this._browseStart = 0
    }
    if (this._browseTimer) { clearInterval(this._browseTimer); this._browseTimer = null }
  }
  ArticleNoticeHandler.prototype._resumeBrowseTrack = function () {
    if (!this._overlay || this._reported) return
    this._browseStart = Date.now()
    var self = this
    this._browseTimer = setInterval(function () { self._tickBrowseTime() }, 1000)
  }
  ArticleNoticeHandler.prototype._onVisibilityChange = function () {
    if (!this._overlay) return
    if (document.hidden) {
      this._pauseBrowseTrack()
    } else {
      this._resumeBrowseTrack()
    }
  }

  ArticleNoticeHandler.prototype.destroy = function () {
    this._clearCountdown()
    this._pauseBrowseTrack()
    document.removeEventListener('visibilitychange', this._handleVisibilityChange)
    if (this._overlay && this._overlay.parentNode) {
      this._overlay.parentNode.removeChild(this._overlay)
    }
    this._overlay = null
    this._closeBtn = null
    this._countdownEl = null
    this._countdownSecondEl = null
    this._actionBtns = null
  }

  _handlers[31] = ArticleNoticeHandler

  // ====================================================================
  //  function=32  跑马灯 Handler
  // ====================================================================
  var MARQUEE_HEIGHT = 40 // px
  var _marqueeCount = { top: 0, bottom: 0 }
  var _marqueeOrigPad = { top: null, bottom: null }

  function _applyMarqueePadding () {
    var cs = document.body.currentStyle || getComputedStyle(document.body)
    var sides = ['top', 'bottom']
    for (var i = 0; i < sides.length; i++) {
      var side = sides[i]
      if (_marqueeCount[side] > 0) {
        // 首次渲染时记住原始 padding
        if (_marqueeOrigPad[side] === null) {
          _marqueeOrigPad[side] = parseInt(cs['padding-' + side], 10) || 0
        }
        document.body.style['padding' + side.charAt(0).toUpperCase() + side.slice(1)] =
          (_marqueeOrigPad[side] + MARQUEE_HEIGHT) + 'px'
      } else if (_marqueeOrigPad[side] !== null) {
        // 全部销毁时还原原始 padding
        var prop = 'padding' + side.charAt(0).toUpperCase() + side.slice(1)
        document.body.style[prop] = _marqueeOrigPad[side] > 0 ? _marqueeOrigPad[side] + 'px' : ''
        _marqueeOrigPad[side] = null
      }
    }
  }

  function _updateFloatCardBottom () {
    var cards = document.querySelectorAll('.yto-float-card')
    if (!cards.length) return
    var bottomOffset = 30
    if (_marqueeCount.bottom > 0) bottomOffset += MARQUEE_HEIGHT
    for (var i = 0; i < cards.length; i++) {
      cards[i].style.bottom = bottomOffset + 'px'
    }
  }

  function MarqueeHandler (config) {
    this._theme = config.theme
    this._onBeforeOpen = config.onBeforeOpen || null
    this._onAfterClose = config.onAfterClose || null
    this._reportConfig = config.reportConfig || null
    this._position = config.position || 'top'
    // 挂载容器：CSS 选择器字符串或 DOM 元素，不传则用 document.body
    this._mountTarget = config.container || null
    this._queue = null
    this._queueIndex = 0
    this._bar = null
    this._marqueeAnimation = null
    this._reported = false
    this._reachAchieved = false
    this._browseStart = 0
    this._browseAccumulated = 0
    this._browseTimer = null
    this._browseRequired = 0
    this._resultConfirmed = 0
    this._frequency = ''
    this._reportData = null
    this._handleVisibilityChange = this._onVisibilityChange.bind(this)
    this._resizeTimer = null
    this._boundResizeHandler = null
  }

  MarqueeHandler.prototype.render = function (itemList) {
    var self = this
    if (!itemList || !itemList.length) return
    if (itemList.length > 1 && !this._queue) {
      this._queue = itemList
      this._queueIndex = 0
    }
    var item = this._queue ? this._queue[this._queueIndex] : itemList[0]
    if (!item) return
    var detail = item.detail || {}
    if (this._onBeforeOpen) this._onBeforeOpen(detail)

    // 记录该条目的展示时间戳，用于单条静默判断
    if (item.id) _setUseTime(item.id)

    this._reportData = {
      msgPublishId: item.id,
      functionType: item.function || 32,
      mpUpdateTime: getNowFormat()
    }
    var FREQ_MAP = { 4: '单次', 0: '每次', 1: '周期', 2: '周期', 3: '周期', 5: '周期' }
    var freqUnit = item.frequency_unit != null ? item.frequency_unit : detail.frequency_unit
    this._frequency = FREQ_MAP[freqUnit] || ''
    var rc = item.result_confirmed != null ? item.result_confirmed : detail.result_confirmed
    this._resultConfirmed = rc != null ? rc : 0
    this._reported = false
    this._reachAchieved = false
    this._browseRequired = (this._resultConfirmed === 3) ? (detail.ie_time || 0) : 0

    var forceRead = detail.force_read === 1
    var content = detail.content || ''
    var attachInfo = detail.attach_info || {}
    var jumpType = attachInfo.jumpType != null ? attachInfo.jumpType : 0
    var mountLink = attachInfo.mountLink || ''

    // 跑马灯条
    var bar = el('div', 'yto-marquee-bar yto-marquee-' + this._position)
    bar.style.setProperty('--yto-primary', this._theme.primary)
    this._bar = bar

    // 小喇叭图标（Material Design volume_up SVG）
    var iconSpan = el('span', 'yto-marquee-icon', { html: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M18 11v2h4v-2h-4zm-2 6.61c.96.71 2.21 1.65 3.2 2.39.4-.53.8-1.07 1.2-1.6-.99-.74-2.24-1.68-3.2-2.4-.4.54-.8 1.08-1.2 1.61zM20.4 5.6c-.4-.53-.8-1.07-1.2-1.6-.99.74-2.24 1.68-3.2 2.4.4.53.8 1.07 1.2 1.6.96-.72 2.21-1.65 3.2-2.4zM4 9c-1.1 0-2 .9-2 2v2c0 1.1.9 2 2 2h1v4h2v-4h1l5 5V5L8 9H4zm11.5 3c0-1.33-.58-2.53-1.5-3.35v6.69c.92-.81 1.5-2.01 1.5-3.34z"/></svg>' })
    bar.appendChild(iconSpan)

    // 文字容器
    var container = el('div', 'yto-marquee-container')
    this._container = container

    // 滚动包裹（双 span 结构，对齐 pcMarqueePreview）
    var scrollWrap = el('div', 'yto-marquee-scroll')
    var textEl1 = el('span', 'yto-marquee-text')
    textEl1.textContent = content
    var textEl2 = el('span', 'yto-marquee-text')
    textEl2.textContent = content
    textEl2.setAttribute('aria-hidden', 'true')
    scrollWrap.appendChild(textEl1)
    scrollWrap.appendChild(textEl2)
    scrollWrap._textEl1 = textEl1
    scrollWrap._textEl2 = textEl2

    // 跳转链接绑定在第一份 span 上
    if (mountLink) {
      textEl1.classList.add('yto-marquee-text-link')
      textEl1.addEventListener('click', function () {
        self._onTextClick(mountLink, jumpType)
      })
    }

    container.appendChild(scrollWrap)
    this._scrollWrap = scrollWrap
    bar.appendChild(container)

    // hover 暂停 / 恢复（Web Animations API）
    bar.addEventListener('mouseenter', function () { self._pauseMarquee() })
    bar.addEventListener('mouseleave', function () { self._resumeMarquee() })

    // 关闭按钮
    if (!forceRead) {
      var closeBtn = el('button', 'yto-marquee-close', { html: '&times;' })
      closeBtn.addEventListener('click', function () { self._close() })
      bar.appendChild(closeBtn)
    }

    // 解析挂载容器（用作定位参考）
    var mountEl = null
    if (this._mountTarget) {
      if (typeof this._mountTarget === 'string') {
        var posSelector = this._mountTarget + '-' + this._position
        mountEl = document.querySelector(posSelector) || document.querySelector(this._mountTarget)
      } else if (this._mountTarget.nodeType) {
        mountEl = this._mountTarget
      }
    }

    // 始终挂到 body，保持 fixed 定位
    document.body.appendChild(bar)

    if (mountEl) {
      // 容器参考模式：fixed 定位 + 根据容器位置计算偏移
      mountEl.style.height = MARQUEE_HEIGHT + 'px'
      this._mountEl = mountEl
      this._inContainer = true
      var self = this
      var updatePos = function () {
        if (!self._bar || !mountEl) return
        var rect = mountEl.getBoundingClientRect()
        var vh = window.innerHeight
        self._bar.style.left = rect.left + 'px'
        self._bar.style.width = rect.width + 'px'
        if (self._position === 'top') {
          var top = Math.max(0, rect.top)
          self._bar.style.top = top + 'px'
          self._bar.style.bottom = 'auto'
        } else {
          var bottom = Math.max(0, vh - rect.bottom)
          self._bar.style.bottom = bottom + 'px'
          self._bar.style.top = 'auto'
        }
      }
      this._boundOnResize = updatePos
      this._boundOnScroll = updatePos
      updatePos()
      window.addEventListener('resize', this._boundOnResize)
      window.addEventListener('scroll', this._boundOnScroll, true)
      _marqueeCount[this._position]++
      _updateFloatCardBottom()
    } else {
      // 默认模式：全屏宽度 fixed 定位
      _marqueeCount[this._position]++
      _applyMarqueePadding()
      this._inContainer = false
    }

    // 窗口 resize 时重新测量容器宽度并重建动画（防抖 200ms）
    var self2 = this
    var sw = scrollWrap
    var ct = container
    this._boundResizeHandler = function () {
      if (self2._resizeTimer) clearTimeout(self2._resizeTimer)
      self2._resizeTimer = setTimeout(function () {
        self2._resizeTimer = null
        if (!self2._bar) return
        self2._checkOverflow(sw, ct)
      }, 200)
    }
    window.addEventListener('resize', this._boundResizeHandler)

    // 测量文本宽度，判断是否需要滚动
    this._checkOverflow(scrollWrap, container)

    // 上报
    if (this._reportConfig && this._reportData) {
      if (this._resultConfirmed === 3) {
        this._startBrowseTrack()
        document.addEventListener('visibilitychange', this._handleVisibilityChange)
      }
      this._reportReach()
    }
  }

  MarqueeHandler.prototype._checkOverflow = function (scrollWrap, container) {
    // 取消之前的动画
    if (this._marqueeAnimation) {
      this._marqueeAnimation.cancel()
      this._marqueeAnimation = null
    }

    // 测量单份文本宽度
    var textEl1 = scrollWrap._textEl1
    var textEl2 = scrollWrap._textEl2
    var measure = document.createElement('div')
    measure.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font-size:14px;'
    measure.textContent = textEl1.textContent
    document.body.appendChild(measure)
    var textWidth = measure.offsetWidth
    document.body.removeChild(measure)
    var containerWidth = container.offsetWidth

    if (textWidth <= containerWidth) {
      // 不需要滚动：隐藏第二份 span
      textEl2.style.display = 'none'
      return
    }

    // 需要滚动：设置第二份 span 间距 = 容器宽度
    textEl2.style.marginLeft = containerWidth + 'px'

    var self = this
    var pauseTime = 2000
    // 第一段滚动时间（最小 10s，对齐 pcMarqueePreview）
    var scrollTime1 = Math.max(10, Math.round(textWidth / 50)) * 1000
    // 循环滚动距离 = containerWidth + textWidth，速度 50px/s
    var loopDistance = containerWidth + textWidth
    var loopTime = Math.round(loopDistance / 50) * 1000

    // 循环关键帧：从右侧出现 → 滚动到左侧消失
    var loopKeyframes = [
      { transform: 'translateX(' + containerWidth + 'px)' },
      { transform: 'translateX(-' + textWidth + 'px)' }
    ]

    // 第一段：居左停顿 2s → 滚动到第一份文本完全离开左侧
    self._marqueeAnimation = scrollWrap.animate([
      { offset: 0, transform: 'translateX(0)' },
      { offset: pauseTime / (pauseTime + scrollTime1), transform: 'translateX(0)' },
      { offset: 1, transform: 'translateX(-' + textWidth + 'px)' }
    ], {
      duration: pauseTime + scrollTime1,
      iterations: 1,
      fill: 'none'
    })

    self._marqueeAnimation.onfinish = function () {
      // 第二段（过渡）：从右侧滚入到左侧消失（单次）
      self._marqueeAnimation = scrollWrap.animate(loopKeyframes, {
        duration: loopTime,
        iterations: 1,
        easing: 'linear',
        fill: 'none'
      })

      self._marqueeAnimation.onfinish = function () {
        // 第三段：无限循环，同样的关键帧
        self._marqueeAnimation = scrollWrap.animate(loopKeyframes, {
          duration: loopTime,
          iterations: Infinity,
          easing: 'linear'
        })
      }
    }
  }

  // hover 暂停
  MarqueeHandler.prototype._pauseMarquee = function () {
    if (this._marqueeAnimation) this._marqueeAnimation.pause()
  }

  // hover 恢复
  MarqueeHandler.prototype._resumeMarquee = function () {
    if (this._marqueeAnimation) this._marqueeAnimation.play()
  }

  MarqueeHandler.prototype._onTextClick = function (url, jumpType) {
    if (url) {
      // 有链接：上报 event=3 + 跳转
      if (!this._reported && this._reportConfig && this._reportData) {
        this._report('3')
      }

      if (jumpType === 1) {
        window.location.href = url
      } else {
        openExternal(url)
      }
    }
    // 无链接：不做处理
  }

  MarqueeHandler.prototype._close = function () {
    if (this._reportConfig && this._reportData && !this._reported) {
      if (this._resultConfirmed === 1) {
        this._report('1')
      } else if (this._resultConfirmed === 3) {
        this._report(this._reachAchieved ? '3' : '1')
      }
    }
    this.destroy()
    if (this._queue && this._queueIndex < this._queue.length - 1) {
      this._queueIndex++
      this.render([this._queue[this._queueIndex]])
    } else {
      if (this._onAfterClose) this._onAfterClose()
    }
  }

  MarqueeHandler.prototype._reportReach = function () {
    this._report('0')
  }

  MarqueeHandler.prototype._report = function (eventCode, duration) {
    if (!this._reportConfig || !this._reportData) return
    if (this._reported && eventCode !== '0') return
    if (eventCode !== '0') {
      this._reported = true
      this._pauseBrowseTrack()
    }
    var self = this
    var browseDuration = typeof duration === 'number' ? duration : this._getBrowseDuration()
    detectDeviceInfo().then(function () {
      self._sendReport(eventCode, browseDuration)
    })
  }

  MarqueeHandler.prototype._sendReport = function (eventCode, browseDuration) {
    var payload = {
      msg_publish_id: this._reportData.msgPublishId,
      'function': this._reportData.functionType,
      user_code: this._reportConfig.usercode,
      event: eventCode,
      duration: browseDuration,
      app_version: _deviceInfo.version || '',
      system_platform: _cachedSysInfo.platform,
      device_brand: _deviceInfo.brand || '',
      device_type: _deviceInfo.type || '',
      system_version: _cachedSysInfo.version,
      system_code: this._reportConfig.system || '',
      update_time: this._reportData.mpUpdateTime
    }
    var extra = this._reportConfig.extraParams || {}
    for (var k in extra) {
      if (extra.hasOwnProperty(k) && !payload.hasOwnProperty(k)) {
        payload[k] = extra[k]
      }
    }
    var url = this._reportConfig.reportUrl
    var xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('TOKEN', TOKEN)
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var res = JSON.parse(xhr.responseText)
          if (res.code === 200) {
            console.log('[YtoNotify] 跑马灯上报成功 event=' + eventCode, payload)
          } else {
            console.warn('[YtoNotify] 跑马灯上报返回异常:', res.msg)
          }
        } catch (e) {}
      } else {
        console.warn('[YtoNotify] 跑马灯上报失败 HTTP ' + xhr.status)
      }
    }
    xhr.send(JSON.stringify(payload))
  }

  // ----- 浏览时长追踪 -----
  MarqueeHandler.prototype._tickBrowseTime = function () {
    var dur = this._getBrowseDuration()
    if (this._browseRequired > 0 && dur >= this._browseRequired) {
      this._reachAchieved = true
    }
  }
  MarqueeHandler.prototype._getBrowseDuration = function () {
    var extra = 0
    if (this._browseStart > 0) {
      extra = Math.round((Date.now() - this._browseStart) / 1000)
    }
    return this._browseAccumulated + extra
  }
  MarqueeHandler.prototype._startBrowseTrack = function () {
    this._pauseBrowseTrack()
    this._browseStart = Date.now()
    this._browseAccumulated = 0
    var self = this
    this._browseTimer = setInterval(function () { self._tickBrowseTime() }, 1000)
  }
  MarqueeHandler.prototype._pauseBrowseTrack = function () {
    if (this._browseStart > 0) {
      this._browseAccumulated += Math.round((Date.now() - this._browseStart) / 1000)
      this._browseStart = 0
    }
    if (this._browseTimer) { clearInterval(this._browseTimer); this._browseTimer = null }
  }
  MarqueeHandler.prototype._resumeBrowseTrack = function () {
    if (!this._bar || this._reported) return
    this._browseStart = Date.now()
    var self = this
    this._browseTimer = setInterval(function () { self._tickBrowseTime() }, 1000)
  }
  MarqueeHandler.prototype._onVisibilityChange = function () {
    if (!this._bar) return
    if (document.hidden) this._pauseBrowseTrack()
    else this._resumeBrowseTrack()
  }

  MarqueeHandler.prototype.destroy = function () {
    if (this._marqueeAnimation) {
      this._marqueeAnimation.cancel()
      this._marqueeAnimation = null
    }
    this._pauseBrowseTrack()
    document.removeEventListener('visibilitychange', this._handleVisibilityChange)
    if (this._boundOnResize) {
      window.removeEventListener('resize', this._boundOnResize)
      window.removeEventListener('scroll', this._boundOnScroll, true)
      this._boundOnResize = null
      this._boundOnScroll = null
    }
    if (this._boundResizeHandler) {
      window.removeEventListener('resize', this._boundResizeHandler)
      this._boundResizeHandler = null
    }
    if (this._resizeTimer) {
      clearTimeout(this._resizeTimer)
      this._resizeTimer = null
    }
    if (this._bar && this._bar.parentNode) {
      this._bar.parentNode.removeChild(this._bar)
    }
    if (this._mountEl) {
      this._mountEl.style.height = '0px'
      this._mountEl = null
    }
    if (_marqueeCount[this._position] > 0) {
      _marqueeCount[this._position]--
    }
    if (!this._inContainer) {
      _applyMarqueePadding()
    }
    _updateFloatCardBottom()
    this._bar = null
    this._container = null
  }

  _handlers[32] = MarqueeHandler

  // ====================================================================
  //  function=33  浮窗通知 Handler
  // ====================================================================
  function FloatingHandler (config) {
    this._theme = config.theme
    this._onBeforeOpen = config.onBeforeOpen || null
    this._onAfterClose = config.onAfterClose || null
    this._reportConfig = config.reportConfig || null
    this._queue = null
    this._queueIndex = 0
    this._card = null
    this._reported = false
    this._reachAchieved = false
    this._browseStart = 0
    this._browseAccumulated = 0
    this._browseTimer = null
    this._browseRequired = 0
    this._resultConfirmed = 0
    this._frequency = ''
    this._reportData = null
    this._autoCloseTimer = null
    this._hideTimer = null
    this._animationType = 1
    this._handleVisibilityChange = this._onVisibilityChange.bind(this)
  }

  FloatingHandler.prototype.render = function (itemList) {
    var self = this
    if (!itemList || !itemList.length) return
    if (itemList.length > 1 && !this._queue) {
      this._queue = itemList
      this._queueIndex = 0
    }
    var item = this._queue ? this._queue[this._queueIndex] : itemList[0]
    if (!item) return
    var detail = item.detail || {}
    if (this._onBeforeOpen) this._onBeforeOpen(detail)

    // 记录展示时间戳（单条静默）
    if (item.id) _setUseTime(item.id)

    this._reportData = {
      msgPublishId: item.id,
      functionType: item['function'] || 33,
      mpUpdateTime: getNowFormat()
    }
    var FREQ_MAP = { 4: '单次', 0: '每次', 1: '周期', 2: '周期', 3: '周期', 5: '周期' }
    var freqUnit = item.frequency_unit != null ? item.frequency_unit : detail.frequency_unit
    this._frequency = FREQ_MAP[freqUnit] || ''
    var rc = item.result_confirmed != null ? item.result_confirmed : detail.result_confirmed
    this._resultConfirmed = rc != null ? rc : 0
    this._reported = false
    this._reachAchieved = false
    this._browseRequired = (this._resultConfirmed === 3) ? (detail.ie_time || 0) : 0

    // 动画类型：4=无动画，其余默认上滑
    this._animationType = detail.animation_type || 1
    // 展示方式：1=一直展示，2=自动关闭
    var durationType = detail.duration_type || 1
    var effectDuration = detail.effect_duration || 3

    // 图片 URL + 描述 + 跳转（从 attachment_list 获取）
    var imageUrl = ''
    var picDesc = ''
    var jumpType = 0
    var mountLink = ''
    var attachList = detail.attachment_list || []
    if (attachList && attachList.length && attachList[0]) {
      var firstGroup = attachList[0]
      if (Array.isArray(firstGroup) && firstGroup[0]) {
        imageUrl = firstGroup[0].full_url || ''
        var extraInfo = firstGroup[0].extra_info
        if (extraInfo) {
          picDesc = extraInfo.picDesc || ''
          jumpType = extraInfo.jumpType != null ? extraInfo.jumpType : 0
          mountLink = extraInfo.mountLink || ''
        }
      } else if (firstGroup.full_url) {
        imageUrl = firstGroup.full_url
        if (firstGroup.extra_info) {
          picDesc = firstGroup.extra_info.picDesc || ''
          jumpType = firstGroup.extra_info.jumpType != null ? firstGroup.extra_info.jumpType : 0
          mountLink = firstGroup.extra_info.mountLink || ''
        }
      }
    }
    if (!imageUrl && detail.image) imageUrl = detail.image
    // 描述 fallback
    var desc = picDesc || '暂无描述'

    // 卡片容器
    var card = el('div', 'yto-float-card')
    if (this._animationType === 4) {
      card.classList.add('yto-float-no-animate')
    }
    card.style.setProperty('--yto-primary', this._theme.primary)
    // 底部偏移：如果有底部跑马灯则加上其高度
    var bottomOffset = 30
    if (_marqueeCount && _marqueeCount.bottom > 0) {
      bottomOffset += MARQUEE_HEIGHT
    }
    card.style.bottom = bottomOffset + 'px'
    this._card = card

    // 顶部：文字描述 + 关闭按钮
    var header = el('div', 'yto-float-header')
    var textEl = el('div', 'yto-float-text')
    textEl.textContent = desc
    header.appendChild(textEl)
    var closeBtn = el('button', 'yto-float-close', { html: '&times;' })
    closeBtn.addEventListener('click', function () { self._close() })
    header.appendChild(closeBtn)
    card.appendChild(header)

    // 图片区域
    var imgWrap = el('div', 'yto-float-img-wrap')
    if (imageUrl) {
      var img = document.createElement('img')
      img.src = imageUrl
      img.alt = ''
      img.draggable = false
      // 图片加载失败时显示占位
      img.onerror = function () {
        this.style.display = 'none'
        var ph = el('div', 'yto-float-img-placeholder', { text: '暂无图片' })
        imgWrap.appendChild(ph)
      }
      if (mountLink) {
        imgWrap.classList.add('yto-float-link')
        imgWrap.addEventListener('click', function () {
          self._onLinkClick(mountLink, jumpType)
        })
      }
      imgWrap.appendChild(img)
    } else {
      var placeholder = el('div', 'yto-float-img-placeholder', { text: '暂无图片' })
      imgWrap.appendChild(placeholder)
    }
    card.appendChild(imgWrap)

    document.body.appendChild(card)

    // 入场动画：延迟添加 show class 让 transition 生效
    if (this._animationType !== 4) {
      setTimeout(function () {
        if (self._card) self._card.classList.add('yto-float-show')
      }, 50)
    } else {
      card.style.opacity = '1'
      card.style.transform = 'translateY(0)'
    }

    // 浏览时长追踪（result_confirmed=3）
    if (this._reportConfig && this._reportData) {
      if (this._resultConfirmed === 3) {
        this._startBrowseTrack()
        document.addEventListener('visibilitychange', this._handleVisibilityChange)
      }
      this._reportReach()
    }

    // 自动关闭：duration_type=2 时启用
    if (durationType === 2) {
      this._autoCloseTimer = setTimeout(function () {
        self._close()
      }, effectDuration * 1000)
    }
  }

  FloatingHandler.prototype._onLinkClick = function (url, jumpType) {
    if (!this._reported && this._reportConfig && this._reportData) {
      this._report('3')
    }
    if (url) {
      if (jumpType === 1) {
        window.location.href = url
      } else {
        openExternal(url)
      }
    }
  }

  FloatingHandler.prototype._close = function () {
    if (this._autoCloseTimer) {
      clearTimeout(this._autoCloseTimer)
      this._autoCloseTimer = null
    }
    if (this._reportConfig && this._reportData && !this._reported) {
      if (this._resultConfirmed === 1) {
        this._report('1')
      } else if (this._resultConfirmed === 3) {
        this._report(this._reachAchieved ? '3' : '1')
      }
    }
    var self = this
    // 退出动画：有动画时先 fade-out，延迟后再销毁
    var delay = (this._animationType === 4) ? 0 : 500
    if (this._card) {
      this._card.classList.remove('yto-float-show')
      if (delay > 0) this._card.classList.add('yto-float-hide')
    }
    this._hideTimer = setTimeout(function () {
      self.destroy()
      if (self._queue && self._queueIndex < self._queue.length - 1) {
        self._queueIndex++
        self.render([self._queue[self._queueIndex]])
      } else {
        if (self._onAfterClose) self._onAfterClose()
      }
    }, delay)
  }

  FloatingHandler.prototype._reportReach = function () {
    this._report('0')
  }

  FloatingHandler.prototype._report = function (eventCode, duration) {
    if (!this._reportConfig || !this._reportData) return
    if (this._reported && eventCode !== '0') return
    if (eventCode !== '0') {
      this._reported = true
      this._pauseBrowseTrack()
    }
    var self = this
    var browseDuration = typeof duration === 'number' ? duration : this._getBrowseDuration()
    detectDeviceInfo().then(function () {
      self._sendReport(eventCode, browseDuration)
    })
  }

  FloatingHandler.prototype._sendReport = function (eventCode, browseDuration) {
    var payload = {
      msg_publish_id: this._reportData.msgPublishId,
      'function': this._reportData.functionType,
      user_code: this._reportConfig.usercode,
      event: eventCode,
      duration: browseDuration,
      app_version: _deviceInfo.version || '',
      system_platform: _cachedSysInfo.platform,
      device_brand: _deviceInfo.brand || '',
      device_type: _deviceInfo.type || '',
      system_version: _cachedSysInfo.version,
      system_code: this._reportConfig.system || '',
      update_time: this._reportData.mpUpdateTime
    }
    if (this._reportConfig.extraParams) {
      for (var k in this._reportConfig.extraParams) {
        if (this._reportConfig.extraParams.hasOwnProperty(k)) {
          payload[k] = this._reportConfig.extraParams[k]
        }
      }
    }
    var url = this._reportConfig.reportUrl
    var xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('TOKEN', TOKEN)
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var res = JSON.parse(xhr.responseText)
          if (res.code === 200) {
            console.log('[YtoNotify] 上报成功 event=' + eventCode, payload)
          } else {
            console.warn('[YtoNotify] 上报返回异常:', res.msg)
          }
        } catch (e) { console.warn('[YtoNotify] 上报解析失败:', e) }
      }
    }
    xhr.send(JSON.stringify(payload))
  }

  // --- 浏览时长追踪 ---
  FloatingHandler.prototype._tickBrowseTime = function () {
    var dur = this._getBrowseDuration()
    if (this._browseRequired > 0 && dur >= this._browseRequired) {
      this._reachAchieved = true
    }
  }

  FloatingHandler.prototype._getBrowseDuration = function () {
    var extra = 0
    if (this._browseStart > 0) {
      extra = Math.round((Date.now() - this._browseStart) / 1000)
    }
    return this._browseAccumulated + extra
  }

  FloatingHandler.prototype._startBrowseTrack = function () {
    this._browseStart = Date.now()
    this._browseTimer = setInterval(this._tickBrowseTime.bind(this), 1000)
  }

  FloatingHandler.prototype._pauseBrowseTrack = function () {
    if (this._browseStart > 0) {
      this._browseAccumulated += Math.round((Date.now() - this._browseStart) / 1000)
      this._browseStart = 0
    }
    if (this._browseTimer) { clearInterval(this._browseTimer); this._browseTimer = null }
  }

  FloatingHandler.prototype._resumeBrowseTrack = function () {
    if (this._browseStart === 0 && (this._browseAccumulated > 0 || this._browseRequired > 0)) {
      this._browseStart = Date.now()
      this._browseTimer = setInterval(this._tickBrowseTime.bind(this), 1000)
    }
  }

  FloatingHandler.prototype._onVisibilityChange = function () {
    if (document.hidden) this._pauseBrowseTrack()
    else this._resumeBrowseTrack()
  }

  FloatingHandler.prototype.destroy = function () {
    if (this._autoCloseTimer) {
      clearTimeout(this._autoCloseTimer)
      this._autoCloseTimer = null
    }
    if (this._hideTimer) {
      clearTimeout(this._hideTimer)
      this._hideTimer = null
    }
    this._pauseBrowseTrack()
    document.removeEventListener('visibilitychange', this._handleVisibilityChange)
    if (this._card && this._card.parentNode) {
      this._card.parentNode.removeChild(this._card)
    }
    this._card = null
  }

  _handlers[33] = FloatingHandler

  // ====================================================================
  //  function=34  轮播图 Handler
  // ====================================================================
  function CarouselHandler (config) {
    this._theme = config.theme
    this._onBeforeOpen = config.onBeforeOpen || null
    this._onAfterClose = config.onAfterClose || null
    this._reportConfig = config.reportConfig || null
    this._carouselContainers = config.carouselContainers || null

    // DOM
    this._wrap = null
    this._mountNode = null

    // 轮播状态
    this._slides = []
    this._dots = []
    this._currentIndex = 0
    this._autoTimer = null
    this._interval = 3000
    this._paused = false
    this._realCount = 0

    // 当前展示的数据（用于跳转上报）
    this._slideData = [] // [{ jumpType, mountLink }]

    // 上报
    this._reportData = null
  }

  CarouselHandler.prototype.render = function (itemList) {
    var self = this
    if (!itemList || !itemList.length) return
    var item = itemList[0]
    if (!item) return
    var detail = item.detail || {}

    if (this._onBeforeOpen) this._onBeforeOpen(detail)

    this._reportData = {
      msgPublishId: item.id,
      functionType: item['function'] || 34,
      mpUpdateTime: detail.update_time || getNowFormat()
    }

    var location = detail.location != null ? detail.location : 0
    var interval = (detail.interval || 3) * 1000
    if (interval < 3000) interval = 3000
    if (interval > 30000) interval = 30000
    this._interval = interval

    // 解析 attachment_list
    var attachList = detail.attachment_list || detail.previewAttachmentList || []
    if (!attachList.length) return

    // 解析每张图片的跳转信息
    this._slideData = []
    var slides = []
    for (var i = 0; i < attachList.length; i++) {
      var group = attachList[i]
      var itemData = (group && group[0]) || {}
      var imgUrl = itemData.full_url || ''
      var extraInfo = itemData.extra_info || {}
      var jumpType = extraInfo.jumpType != null ? extraInfo.jumpType : 0
      var mountLink = extraInfo.mountLink || ''
      this._slideData.push({ jumpType: jumpType, mountLink: mountLink })
      slides.push({ url: imgUrl, index: i })
    }

    // 查找挂载容器
    var mountNode = this._findContainer(location)
    if (!mountNode) {
      console.warn('[YtoNotify] function=34 未找到 location=' + location + ' 的容器，跳过渲染')
      if (this._onAfterClose) this._onAfterClose()
      return
    }
    this._mountNode = mountNode

    // 创建轮播容器
    var wrap = el('div', 'yto-banner-wrap')
    this._wrap = wrap
    this._slides = []
    this._dots = []

    // 2 张图时翻倍（AB→ABAB），让轮播始终同向过渡
    this._realCount = slides.length
    if (slides.length === 2) {
      slides = slides.concat(slides.map(function (s) {
        return { url: s.url, index: s.index }
      }))
    }

    // 创建 slides
    for (var s = 0; s < slides.length; s++) {
      ;(function (slideInfo) {
        var slide = el('div', 'yto-banner-slide' + (slideInfo.index === 0 && s === 0 ? ' yto-banner-active' : ''))
        var img = document.createElement('img')
        img.alt = '轮播图' + (slideInfo.index + 1)
        img.draggable = false
        if (slideInfo.url) {
          img.onerror = function () {
            console.error('[YtoNotify] 轮播图加载失败:', this.src)
            this.onerror = null
            this.alt = '图片加载失败'
            this.removeAttribute('src')
          }
          img.src = slideInfo.url
        } else {
          img.alt = '暂无图片'
        }
        slide.appendChild(img)
        wrap.appendChild(slide)
        self._slides.push(slide)
      })(slides[s])
    }

    // 左右箭头 + 指示器（多张图时显示）
    if (this._realCount > 1) {
      var svgLeft = '<svg viewBox="0 0 14 14"><polyline points="9 2 4 7 9 12"/></svg>'
      var svgRight = '<svg viewBox="0 0 14 14"><polyline points="5 2 10 7 5 12"/></svg>'
      var arrowL = el('button', 'yto-banner-arrow yto-banner-arrow-left', { html: svgLeft })
      var arrowR = el('button', 'yto-banner-arrow yto-banner-arrow-right', { html: svgRight })
      arrowL.addEventListener('click', function () { self._prev() })
      arrowR.addEventListener('click', function () { self._next() })
      wrap.appendChild(arrowL)
      wrap.appendChild(arrowR)

      // 指示器按原始数量创建，点击时映射到翻倍后的索引
      var dotsWrap = el('div', 'yto-banner-dots')
      var realLen = this._realCount
      var totalLen = slides.length
      for (var d = 0; d < realLen; d++) {
        ;(function (idx) {
          var dot = el('button', 'yto-banner-dot' + (idx === 0 ? ' yto-banner-dot-active' : ''))
          dot.addEventListener('click', function () {
            var targetIdx = idx
            if (totalLen > realLen) {
              if (self._currentIndex >= realLen) targetIdx = idx + realLen
            }
            self._goTo(targetIdx)
          })
          dotsWrap.appendChild(dot)
          self._dots.push(dot)
        })(d)
      }
      wrap.appendChild(dotsWrap)
    }

    // hover 暂停轮播
    wrap.addEventListener('mouseenter', function () { self._pauseAutoPlay() })
    wrap.addEventListener('mouseleave', function () { self._resumeAutoPlay() })

    // 点击图片跳转（取模映射回原始 slideData）
    wrap.addEventListener('click', function (e) {
      if (e.target.closest('.yto-banner-arrow') || e.target.closest('.yto-banner-dot')) return
      var dataIdx = self._currentIndex % self._slideData.length
      var data = self._slideData[dataIdx]
      if (data && data.mountLink && data.jumpType > 0) {
        self._onImageClick(data.mountLink, data.jumpType)
      }
    })

    // 挂载到容器
    mountNode.innerHTML = ''
    mountNode.appendChild(wrap)

    // 启动自动轮播
    this._currentIndex = 0
    if (slides.length > 1) {
      this._startAutoPlay(interval, slides.length)
    }

    // 上报 event=0（每次显示都上报）
    this._report('0')
  }

  CarouselHandler.prototype._findContainer = function (location) {
    // 1. 配置中的映射
    if (this._carouselContainers) {
      var target = this._carouselContainers[location]
      if (target) {
        if (typeof target === 'string') return document.querySelector(target)
        if (target.nodeType) return target
      }
    }
    // 2. data 属性约定
    var el = document.querySelector('[data-yto-carousel="' + location + '"]')
    if (el) return el
    // 3. ID 约定
    return document.getElementById('yto-carousel-' + location)
  }

  // ----- 轮播控制 -----
  CarouselHandler.prototype._goTo = function (index) {
    if (index === this._currentIndex) return
    var total = this._slides.length
    if (index < 0 || index >= total) return
    var current = this._currentIndex
    var curSlide = this._slides[current]
    var nextSlide = this._slides[index]

    // 判断方向：正向(next) / 反向(prev)，含循环边界
    var forward = index > current
    if (index === 0 && current === total - 1) forward = true
    if (index === total - 1 && current === 0) forward = false

    // 清理所有非当前、非目标的 slide 状态
    for (var i = 0; i < total; i++) {
      if (i !== current && i !== index) {
        this._slides[i].classList.add('yto-banner-no-transition')
        this._slides[i].classList.remove('yto-banner-active', 'yto-banner-slide-left')
        this._slides[i].offsetHeight
        this._slides[i].classList.remove('yto-banner-no-transition')
      }
    }

    if (forward) {
      curSlide.classList.remove('yto-banner-active')
      curSlide.classList.add('yto-banner-slide-left')
      nextSlide.classList.add('yto-banner-no-transition')
      nextSlide.classList.remove('yto-banner-slide-left', 'yto-banner-active')
      nextSlide.offsetHeight
      nextSlide.classList.remove('yto-banner-no-transition')
      nextSlide.classList.add('yto-banner-active')
    } else {
      curSlide.classList.remove('yto-banner-active')
      nextSlide.classList.add('yto-banner-no-transition')
      nextSlide.classList.add('yto-banner-slide-left')
      nextSlide.classList.remove('yto-banner-active')
      nextSlide.offsetHeight
      nextSlide.classList.remove('yto-banner-no-transition', 'yto-banner-slide-left')
      nextSlide.classList.add('yto-banner-active')
    }

    // 同步指示器（取模映射回原始索引）
    var realCount = this._realCount || total
    var curDot = current % realCount
    var nextDot = index % realCount
    if (this._dots.length > 0 && curDot !== nextDot) {
      if (this._dots[curDot]) this._dots[curDot].classList.remove('yto-banner-dot-active')
      if (this._dots[nextDot]) this._dots[nextDot].classList.add('yto-banner-dot-active')
    }

    this._currentIndex = index
    this._restartAutoPlay()
  }

  CarouselHandler.prototype._prev = function () {
    var total = this._slides.length
    this._goTo(this._currentIndex > 0 ? this._currentIndex - 1 : total - 1)
  }

  CarouselHandler.prototype._next = function () {
    var total = this._slides.length
    this._goTo(this._currentIndex < total - 1 ? this._currentIndex + 1 : 0)
  }

  CarouselHandler.prototype._startAutoPlay = function (interval, total) {
    var self = this
    this._stopAutoPlay()
    if (total <= 1 || interval <= 0) return
    this._paused = false
    this._autoTimer = setInterval(function () {
      var next = self._currentIndex < total - 1 ? self._currentIndex + 1 : 0
      self._goTo(next)
    }, interval)
  }

  CarouselHandler.prototype._stopAutoPlay = function () {
    if (this._autoTimer) { clearInterval(this._autoTimer); this._autoTimer = null }
  }

  // hover → clearInterval，标记暂停
  CarouselHandler.prototype._pauseAutoPlay = function () {
    if (this._paused) return
    this._paused = true
    if (this._autoTimer) { clearInterval(this._autoTimer); this._autoTimer = null }
  }

  // 移开 → 从完整间隔重新计时（el-carousel 行为）
  CarouselHandler.prototype._resumeAutoPlay = function () {
    if (!this._paused || this._slides.length <= 1) return
    this._startAutoPlay(this._interval, this._slides.length)
  }

  CarouselHandler.prototype._restartAutoPlay = function () {
    this._stopAutoPlay()
    if (this._slides.length > 1) {
      this._startAutoPlay(this._interval, this._slides.length)
    }
  }

  // ----- 图片点击跳转 + 上报 -----
  CarouselHandler.prototype._onImageClick = function (url, jumpType) {
    // 上报 event=3（点击跳转）
    this._report('3')

    if (jumpType === 1) {
      window.location.href = url
    } else if (jumpType === 2) {
      window.open(url, '_blank')
    }
  }

  // ----- 上报 -----
  CarouselHandler.prototype._report = function (eventCode) {
    if (!this._reportConfig || !this._reportData) return
    // event=0 允许多次上报，event=3 也允许多次（每次点击）
    var self = this
    detectDeviceInfo().then(function () {
      self._sendReport(eventCode)
    })
  }

  CarouselHandler.prototype._sendReport = function (eventCode) {
    var payload = {
      msg_publish_id: this._reportData.msgPublishId,
      'function': this._reportData.functionType,
      user_code: this._reportConfig.usercode,
      event: eventCode,
      duration: 0,
      app_version: _deviceInfo.version || '',
      system_platform: _cachedSysInfo.platform,
      device_brand: _deviceInfo.brand || '',
      device_type: _deviceInfo.type || '',
      system_code: this._reportConfig.system || '',
      system_version: _cachedSysInfo.version,
      update_time: this._reportData.mpUpdateTime
    }
    if (this._reportConfig.extraParams) {
      for (var k in this._reportConfig.extraParams) {
        if (this._reportConfig.extraParams.hasOwnProperty(k)) {
          payload[k] = this._reportConfig.extraParams[k]
        }
      }
    }
    var url = this._reportConfig.reportUrl
    var xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('TOKEN', TOKEN)
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var res = JSON.parse(xhr.responseText)
          if (res.code === 200) {
            console.log('[YtoNotify] 上报成功 event=' + eventCode, payload)
          } else {
            console.warn('[YtoNotify] 上报返回异常:', res.msg)
          }
        } catch (e) { console.warn('[YtoNotify] 上报解析失败:', e) }
      }
    }
    xhr.send(JSON.stringify(payload))
  }

  // ----- 销毁 -----
  CarouselHandler.prototype.destroy = function () {
    this._stopAutoPlay()
    if (this._wrap && this._wrap.parentNode) {
      this._wrap.parentNode.removeChild(this._wrap)
    }
    this._wrap = null
    this._mountNode = null
    this._slides = []
    this._dots = []
    this._slideData = []
  }

  _handlers[34] = CarouselHandler

  // ====================================================================
  //  静默时长：localStorage 缓存 useTime
  // ====================================================================
  var SILENCE_KEY = 'yto_notify_useTime'

  function _getUseTimeMap () {
    try {
      var v = localStorage.getItem(SILENCE_KEY)
      return v ? JSON.parse(v) : {}
    } catch (e) { return {} }
  }

  function _setUseTime (itemId) {
    try {
      var map = _getUseTimeMap()
      map[itemId] = Date.now()
      localStorage.setItem(SILENCE_KEY, JSON.stringify(map))
    } catch (e) {}
  }

  function _isInSilence (itemId, silenceTime) {
    var map = _getUseTimeMap()
    var lastUse = map[itemId]
    if (!lastUse) return false
    return (Date.now() - lastUse) < silenceTime
  }

  // ====================================================================
  //  核心 SDK：负责网络请求 + 按 functionType 分发到对应 Handler
  // ====================================================================
  function NotifySDK (config) {
    this._baseUrl = (config.baseUrl || '').replace(/\/+$/, '') + '/'
    this._system = config.system || ''
    this._usercode = config.usercode || ''
    this._reportUrl = config.reportUrl || (this._baseUrl + 'v2/info/pc/api/event/')
    this._extraReportParams = config.extraReportParams || null
    this._onBeforeOpen = typeof config.onBeforeOpen === 'function' ? config.onBeforeOpen : null
    this._onAfterClose = typeof config.onAfterClose === 'function' ? config.onAfterClose : null
    this._theme = resolveTheme(config)

    // container：跑马灯挂载容器（CSS 选择器或 DOM 元素），不传则挂到 document.body
    this._container = config.container || null

    // carouselContainers：轮播图挂载容器映射 { location: selector|DOMElement }
    this._carouselContainers = config.carouselContainers || null

    // functionTypes 数组，必填
    this._functionTypes = Array.isArray(config.functionTypes) ? config.functionTypes : []

    // 静默时长（毫秒），默认 15 分钟
    this._silenceTime = (typeof config.silenceTime === 'number' && config.silenceTime >= 0)
      ? config.silenceTime : 15 * 60 * 1000

    this._activeHandlers = []
  }

  /**
   * 请求接口，有数据则分发给对应 Handler 渲染
   * 多个 functionType 并行请求，结果合并为统一队列，逐条弹框
   */
  NotifySDK.prototype.init = function () {
    var self = this
    injectCSS()
    if (!this._functionTypes.length) {
      console.warn('[YtoNotify] 未指定 functionTypes，无法初始化')
      return this
    }

    // 并行请求所有 functionType 的数据
    var fetchPromises = this._functionTypes.map(function (fnType) {
      var HandlerClass = _handlers[fnType]
      if (!HandlerClass) {
        console.warn('[YtoNotify] 未注册 function=' + fnType + ' 的处理器')
        return Promise.resolve([])
      }
      return self._fetchData(fnType).then(function (list) {
        // 给每条数据标记 handler 类型
        return (Array.isArray(list) ? list : []).map(function (item) {
          return { item: item, fnType: fnType }
        })
      }).catch(function (err) {
        console.error('[YtoNotify] function=' + fnType + ' 请求失败:', err)
        return []
      })
    })

    Promise.all(fetchPromises).then(function (results) {
      // 按类型分流：弹窗队列(30/31) / 顶部跑马灯(32 pos=1) / 底部跑马灯(32 pos=2) / 浮窗通知(33) / 轮播图(34)
      var popupQueue = []
      var topMarqueeItems = []
      var bottomMarqueeItems = []
      var floatItems = []
      var carouselItems = []

      results.forEach(function (group) {
        group.forEach(function (entry) {
          var itemId = entry.item.id
          // 单条数据静默检查：仅弹窗(30/31)生效，跑马灯(32)、浮窗(33)、轮播图(34)不受静默限制
          if (entry.fnType !== 32 && entry.fnType !== 33 && entry.fnType !== 34 && itemId && _isInSilence(itemId, self._silenceTime)) {
            console.log('[YtoNotify] 条目 ' + itemId + ' 在静默期内，跳过')
            return
          }
          if (entry.fnType === 34) {
            carouselItems.push(entry.item)
          } else if (entry.fnType === 33) {
            floatItems.push(entry.item)
          } else if (entry.fnType === 32) {
            var pos = (entry.item.detail || {}).display_position
            if (pos === 1) topMarqueeItems.push(entry.item)
            else if (pos === 2) bottomMarqueeItems.push(entry.item)
          } else {
            popupQueue.push(entry)
          }
        })
      })

      // 流计数器：所有流结束后触发 onAfterClose
      var activeStreams = 0
      function streamDone () {
        activeStreams--
        if (activeStreams <= 0 && self._onAfterClose) {
          self._onAfterClose()
        }
      }

      var reportCfg = {
        reportUrl: self._reportUrl,
        usercode: self._usercode,
        extraParams: self._extraReportParams,
        system: self._system
      }

      // ---- 弹窗队列 (function 30 / 31) ----
      if (popupQueue.length) {
        activeStreams++
        var currentIndex = 0

        var queueManager = {
          advance: function () {
            currentIndex++
            if (currentIndex < popupQueue.length) {
              showNext()
            } else {
              streamDone()
            }
          }
        }

        function showNext () {
          var entry = popupQueue[currentIndex]
          var HandlerClass = _handlers[entry.fnType]
          if (!HandlerClass) {
            queueManager.advance()
            return
          }
          var handler = new HandlerClass({
            theme: self._theme,
            onBeforeOpen: self._onBeforeOpen,
            onAfterClose: null,
            reportConfig: reportCfg
          })
          handler._queueManager = queueManager
          self._activeHandlers.push(handler)
          handler.render([entry.item])
          _setUseTime(entry.item.id)
        }

        showNext()
      }

      // ---- 顶部跑马灯 (function 32, display_position=1) ----
      if (topMarqueeItems.length) {
        activeStreams++
        var topHandler = new _handlers[32]({
          theme: self._theme,
          onBeforeOpen: self._onBeforeOpen,
          onAfterClose: streamDone,
          reportConfig: reportCfg,
          position: 'top',
          container: self._container
        })
        self._activeHandlers.push(topHandler)
        topHandler.render(topMarqueeItems)
      }

      // ---- 底部跑马灯 (function 32, display_position=2) ----
      if (bottomMarqueeItems.length) {
        activeStreams++
        var bottomHandler = new _handlers[32]({
          theme: self._theme,
          onBeforeOpen: self._onBeforeOpen,
          onAfterClose: streamDone,
          reportConfig: reportCfg,
          position: 'bottom',
          container: self._container
        })
        self._activeHandlers.push(bottomHandler)
        bottomHandler.render(bottomMarqueeItems)
      }

      // ---- 浮窗通知 (function 33) ----
      if (floatItems.length) {
        activeStreams++
        var floatHandler = new _handlers[33]({
          theme: self._theme,
          onBeforeOpen: self._onBeforeOpen,
          onAfterClose: streamDone,
          reportConfig: reportCfg
        })
        self._activeHandlers.push(floatHandler)
        floatHandler.render(floatItems)
      }

      // ---- 轮播图 (function 34) ----
      if (carouselItems.length) {
        for (var ci = 0; ci < carouselItems.length; ci++) {
          activeStreams++
          var carouselHandler = new _handlers[34]({
            theme: self._theme,
            onBeforeOpen: self._onBeforeOpen,
            onAfterClose: streamDone,
            reportConfig: reportCfg,
            carouselContainers: self._carouselContainers
          })
          self._activeHandlers.push(carouselHandler)
          carouselHandler.render([carouselItems[ci]])
        }
      }

      // 无任何数据流时直接回调
      if (activeStreams === 0 && self._onAfterClose) {
        self._onAfterClose()
      }
    })

    return this
  }

  /**
   * 手动销毁所有活跃 Handler
   */
  NotifySDK.prototype.destroy = function () {
    this._activeHandlers.forEach(function (h) { h.destroy() })
    this._activeHandlers = []
  }

  /**
   * 网络请求
   */
  NotifySDK.prototype._fetchData = function (fnType) {
    var url = this._baseUrl + 'v2/info/pc/api/' + fnType
      + '/?system=' + encodeURIComponent(this._system)
      + '&usercode=' + encodeURIComponent(this._usercode)

    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest()
      xhr.open('GET', url, true)
      xhr.setRequestHeader('TOKEN', TOKEN)
      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) return
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            var res = JSON.parse(xhr.responseText)
            if (res.code === 200 && res.result) {
              resolve(res.result)
            } else {
              reject(new Error(res.msg || '接口返回异常'))
            }
          } catch (e) { reject(e) }
        } else {
          reject(new Error('HTTP ' + xhr.status))
        }
      }
      xhr.onerror = function () { reject(new Error('网络错误')) }
      xhr.send()
    })
  }

  // ====================================================================
  //  对外暴露（UMD factory return）
  // ====================================================================
  return {
    /**
     * 初始化并自动展示
     * @param {Object} config - { baseUrl, system, usercode, functionTypes, reportUrl?, extraReportParams?, themeColor?, onBeforeOpen?, onAfterClose? }
     * @returns {NotifySDK} 实例，可调用 .destroy() 手动销毁
     */
    init: function (config) {
      var instance = new NotifySDK(config)
      instance.init()
      return instance
    },
    /**
     * 创建实例但不自动调用，需手动 instance.init()
     */
    create: function (config) {
      return new NotifySDK(config)
    },
    /**
     * 注册新的场景 Handler
     * @param {number} functionId - 接口 function 编号
     * @param {Function} HandlerClass - 构造函数，需实现 render(itemList) 和 destroy()
     *
     * Handler 构造函数签名：
     *   function MyHandler(config) {}
     *   config.theme       — { primary, light, lighter } 主题色三阶
     *   config.onBeforeOpen — 弹框打开前回调
     *   config.onAfterClose — 弹框关闭后回调
     *   config.reportConfig — { reportUrl, usercode, extraParams } 上报配置
     *   MyHandler.prototype.render(itemList) — itemList 为接口返回的 result 数组
     *   MyHandler.prototype.destroy()        — 清理 DOM 和定时器
     */
    register: function (functionId, HandlerClass) {
      _handlers[functionId] = HandlerClass
    },
    /**
     * 获取已注册的 Handler 列表
     */
    getRegistered: function () {
      var keys = []
      for (var k in _handlers) { if (_handlers.hasOwnProperty(k)) keys.push(+k) }
      return keys
    }
  }

});