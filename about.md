---
layout: article
titles:
  en      : &EN
  en-GB   : *EN
  en-US   : *EN
  en-CA   : *EN
  en-AU   : *EN
  zh-Hans : &ZH_HANS
  zh      : *ZH_HANS
  zh-CN   : *ZH_HANS
  zh-SG   : *ZH_HANS
  zh-Hant : &ZH_HANT
  zh-TW   : *ZH_HANT
  zh-HK   : *ZH_HANT
  ko      : &KO
  ko-KR   : *KO
  fr      : &FR
  fr-BE   : *FR
  fr-CA   : *FR
  fr-CH   : *FR
  fr-FR   : *FR
  fr-LU   : *FR
key: page-about
---

<style>
.profile-header {
  text-align: center;
  padding: 2.5rem 1rem;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 2rem;
  border-left: 4px solid #667eea;
  transition: all 0.3s ease;
}

.profile-header:hover {
  transform: translateX(5px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.profile-header h1 {
  margin: 0;
  font-size: 2.5rem;
  font-weight: 400;
  color: #333;
  letter-spacing: 1px;
}

.profile-header p {
  margin: 1rem 0 0 0;
  font-size: 1rem;
  color: #667eea;
  font-weight: 400;
}

.insight-card {
  background: #f8f9fa;
  padding: 2rem;
  border-radius: 8px;
  margin: 2rem 0;
  border-left: 4px solid #667eea;
  transition: all 0.3s ease;
}

.insight-card:hover {
  transform: translateX(5px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.insight-card h3 {
  margin-top: 0;
  color: #667eea;
  font-size: 1.3rem;
}

.journey-timeline {
  position: relative;
  padding-left: 2rem;
  margin: 2rem 0;
}

.journey-item {
  position: relative;
  padding: 1.5rem;
  margin-bottom: 2rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transition: all 0.3s ease;
}

.journey-item:before {
  content: '';
  position: absolute;
  left: -2rem;
  top: 1.5rem;
  width: 12px;
  height: 12px;
  background: #667eea;
  border-radius: 50%;
  border: 3px solid white;
  box-shadow: 0 0 0 2px #667eea;
}

.journey-item:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.journey-item h4 {
  margin: 0 0 0.5rem 0;
  color: #333;
  font-size: 1.2rem;
}

.journey-item p {
  margin: 0.5rem 0;
  color: #666;
  line-height: 1.7;
}

.focus-area {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.focus-card {
  padding: 1.5rem;
  background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
  border-radius: 8px;
  border: 1px solid #667eea30;
  transition: all 0.3s ease;
}

.focus-card:hover {
  transform: translateY(-5px);
  border-color: #667eea;
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.15);
}

.focus-card h4 {
  margin: 0 0 1rem 0;
  color: #667eea;
  font-size: 1.1rem;
}

.focus-card p {
  margin: 0;
  color: #555;
  line-height: 1.6;
  font-size: 0.95rem;
}

@media (max-width: 768px) {
  .profile-header h1 {
    font-size: 1.8rem;
  }

  .journey-timeline {
    padding-left: 1.5rem;
  }

  .focus-area {
    grid-template-columns: 1fr;
  }
}
</style>

<div class="profile-header">
  <h1>Chuan</h1>
  <p>记录光阴 · 分享热爱 · 探索未知</p>
</div>

## 关于我

一个喜欢钻研技术细节的工程师。如果你也和我一样，相信魔鬼藏在细节里，享受在代码的迷宫中寻找出口的乐趣，那么希望我的文章能为你带来一些启发，也期待你的留言与探讨。


## 关于这个博客

这里是我的技术笔记本，记录了：

- **系统底层探索**：虚拟内存分类、链接过程剖析、进程控制机制
- **框架原理解析**：Qt 信号槽实现、GNU Radio 调度器、事件循环机制
- **信号处理实践**：多相信道化、跳频处理、滤波器设计
- **AI 工具研究**：MCP 协议分析、Claude Code 机制、Agent 开发实践
- **工程经验总结**：性能优化、静态分析、抓包调试技巧

**写作风格**：技术务实，拒绝浮夸。每篇文章都力求"讲清楚原理、给出可验证的代码、分享踩坑经验"。

## 联系方式

- **博客**：[noonafter.cn](https://noonafter.cn)
- **GitHub**：[@noonafter](https://github.com/noonafter)

---

<div style="text-align: center; color: #666; font-size: 0.9rem; margin-top: 3rem; padding: 2rem 0; border-top: 1px solid #eee;">
  <p style="font-size: 1rem; margin-bottom: 0.5rem;">「钻研技术，坚持分享，持续成长」</p>
  <p style="font-size: 0.85rem; color: #999;">技术的深度来自持续的追问 · 成长的轨迹藏在每一篇博客里</p>
</div>
