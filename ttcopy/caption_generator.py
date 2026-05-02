"""小红书文案生成器 —— 基于场景描述生成标题和描述。

优先使用 OPENAI_API_KEY 调用 GPT-4o 生成高质量文案。
未配置 API key 时，使用内置 fallback 模板生成基础版文案。
"""

import os


def generate_caption(scene_description: str) -> tuple[str, str]:
    """
    根据视频场景描述生成小红书风格的标题和描述。

    Args:
        scene_description: 对视频画面/内容的文字描述。

    Returns:
        (title, description) 元组。
    """
    api_key = os.environ.get("OPENAI_API_KEY")

    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)

            prompt = (
                "你是一位小红书爆款笔记创作者。请根据以下视频内容描述，"
                "生成一个吸引人的视频标题和笔记描述。\n\n"
                "要求：\n"
                "- 标题：15-25字，带1-2个emoji，有冲击力或悬念感\n"
                "- 描述：口语化、真实分享感，100字以内，结尾带3-5个相关话题标签\n"
                "- 风格：像朋友安利，不要营销感太重\n\n"
                f"视频内容描述：{scene_description}\n\n"
                "请严格按以下格式返回，不要添加额外解释：\n"
                "标题：<标题>\n"
                "描述：<描述>"
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=300,
            )

            text = response.choices[0].message.content.strip()
            title = ""
            description = ""
            for line in text.split("\n"):
                if line.startswith("标题："):
                    title = line.replace("标题：", "").strip()
                elif line.startswith("描述："):
                    description = line.replace("描述：", "").strip()

            if title and description:
                return title, description

        except Exception as e:
            print(f"[OpenAI 生成失败，使用 fallback] {e}")

    # Fallback：基础文案生成（无 API key 时的兜底方案）
    return _fallback_generate(scene_description)


def _fallback_generate(desc: str) -> tuple[str, str]:
    """无 OpenAI key 时的基础文案生成。"""
    core = desc.strip()
    if len(core) > 50:
        core = core[:50] + "..."

    # 简单关键词匹配生成话题标签
    tags = _extract_tags(desc)

    # 标题：取前 12 字 + 情绪后缀
    headline = core[:12] if len(core) > 12 else core
    title = f"✨ {headline}... 这也太绝了吧！"

    # 描述：口语化包装
    description = (
        f"刚刷到这个视频，真的有被惊艳到！\n\n"
        f"{desc}\n\n"
        f"家人们快来看👀 {tags}"
    )

    return title, description


def _extract_tags(text: str) -> str:
    """从描述中简单匹配关键词，生成话题标签。"""
    keyword_map = {
        "猫": "#猫咪日常 #萌宠",
        "狗": "#狗狗 #萌宠",
        "美食": "#美食分享 #深夜放毒",
        "篮球": "#篮球 #运动",
        "足球": "#足球 #体育",
        "跳舞": "#舞蹈 #节奏感",
        "风景": "#风景 #旅行",
        "车": "#汽车 #速度与激情",
        "搞笑": "#搞笑 #爆笑",
        "科技": "#科技 #数码",
        "游戏": "#游戏 #电竞",
        "健身": "#健身 #自律",
        "萌": "#萌宠 #可爱",
        "惊": "#震惊 #不可思议",
    }

    matched = []
    for kw, tag in keyword_map.items():
        if kw in text and tag not in matched:
            matched.append(tag)

    if not matched:
        matched.append("#tiktok搬运 #视频分享")

    return " ".join(matched[:3])
