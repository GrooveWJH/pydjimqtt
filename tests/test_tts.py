import pyttsx3

engine = pyttsx3.init()

# --- 调整语速 ---
rate = engine.getProperty('rate')   # 获取当前语速
print(f"当前语速: {rate}")
engine.setProperty('rate', rate - 50) # 减慢语速

# --- 调整音量 ---
volume = engine.getProperty('volume') # 获取当前音量 (0.0 到 1.0)
print(f"当前音量: {volume}")
engine.setProperty('volume', 1.0)     # 设置最大音量

# --- 切换语音（男声/女声）---
voices = engine.getProperty('voices')
print(f"系统中有 {len(voices)} 种语音:")

# -----------------
#  核心修改：查找并设置中文语音
# -----------------
chinese_voice_id = None
for v in voices:
    print(f"  ID: {v.id}")
    print(f"  Name: {v.name}")
    print(f"  Lang: {v.languages}")
    
    # v.languages 是一个列表，例如 ['zh_CN'] 或 ['en_US']
    for lang in v.languages:
        # 检查语言代码是否以 'zh' 开头 (包括 zh_CN, zh_TW, zh_HK)
        if lang.lower().startswith('zh'):
            chinese_voice_id = v.id
            print(f"--- 找到了中文语音: {v.name} ({lang}) ---")
            break  # 停止搜索此语音的更多语言
    
    if chinese_voice_id:
        break  # 找到了一个中文语音，停止搜索其他语音

# 检查是否找到了中文语音
if chinese_voice_id:
    print(f"已设置语音 ID 为: {chinese_voice_id}")
    engine.setProperty('voice', chinese_voice_id)
else:
    print("警告：未在系统中找到中文语音包，将使用默认语音。")

# 朗读
print("\n即将开始朗读中文...")
engine.say("任务开始！")


engine.runAndWait()
print("朗读完毕。")