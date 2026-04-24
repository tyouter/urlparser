# Multi-Platform Transcription Test Report

> Date: 2026-04-23
> Strategy: bb-browser (CDP) + FunASR
> Key: bb-browser fetch bypasses Bilibili 412

## Results

| # | Platform | Name | Type | Fetch | Transcribe | Text Length |
|---|----------|------|------|-------|------------|-------------|
| 1 | bilibili | 爆肝5小时实测国产大模型横评 | video | PASS | PASS | 2358 |
| 2 | bilibili | ObsidianCLI+ClaudeCode笔记工 | video | PASS | PASS | 1678 |
| 3 | bilibili | 开源Figma-AI原生设计编辑器OpenPenc | video | PASS | PASS | 482 |
| 4 | zhihu | claude.md怎么写才能让Claude Cod | article | PASS | SKIP | 7684 |
| 5 | zhihu | 普通人第一次用OpenClaw应该注意什么 | article | PASS | SKIP | 940 |
| 6 | zhihu | 最难调试修复的bug是怎样的 | article | PASS | SKIP | 5636 |
| 7 | weixin | 龙虾越火越应该研究Skill | article | PASS | SKIP | 5485 |
| 8 | weixin | 微信公众号文章2 | article | PASS | SKIP | 4838 |
| 9 | zhihu_zhuanlan | 知乎专栏-PlaywrightCLI隐藏技能 | article | PASS | SKIP | 3916 |

## Summary

- Fetch: 9/9 PASS
- Transcription (video): 3 PASS
- Content saved (article): 9 PASS

## Completeness Verification

| # | Platform | Name | Type | Chars/Sec | Assessment |
|---|----------|------|------|-----------|------------|
| 1 | bilibili | 爆肝5小时实测国产大模型横评 | video | 5.05 | GOOD |
| 2 | bilibili | ObsidianCLI+ClaudeCode笔记工 | video | 5.01 | GOOD |
| 3 | bilibili | 开源Figma-AI原生设计编辑器OpenPenc | video | 5.43 | GOOD |
| 4 | zhihu | claude.md怎么写才能让Claude Cod | article | 7684 chars | GOOD |
| 5 | zhihu | 普通人第一次用OpenClaw应该注意什么 | article | 940 chars | GOOD |
| 6 | zhihu | 最难调试修复的bug是怎样的 | article | 5636 chars | GOOD |
| 7 | weixin | 龙虾越火越应该研究Skill | article | 5485 chars | GOOD |
| 8 | weixin | 微信公众号文章2 | article | 4838 chars | GOOD |
| 9 | zhihu_zhuanlan | 知乎专栏-PlaywrightCLI隐藏技能 | article | 3916 chars | GOOD |

## Overall: ALL PASS
