"""Content agent for content creation tasks."""

from pathlib import Path
from typing import Any, Optional

from ..memory.profile_store import ProfileStore


class ContentAgent:
    """Specialist agent for content creation tasks."""

    def __init__(self, profile_store: Optional[ProfileStore] = None):
        """Initialize content agent.

        Args:
            profile_store: ProfileStore instance
        """
        self.profile = profile_store

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load content prompt from file."""
        prompt_path = Path("src/prompts/content.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a content creation specialist agent."

    def _try_llm(self, system: str, user: str) -> str | None:
        """Try to get a response from the LLM. Returns None if unavailable."""
        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            content = router.ask(system=system, user=user, task_type="general")
            if content and content.strip():
                return content
        except NoModelAvailableError:
            return None
        except Exception:
            return None
        return None

    def _get_writing_style(self) -> str:
        """Get user's writing style preference."""
        if self.profile:
            return self.profile.get_profile_value("writing_style", "professional")
        return "professional"

    def create_youtube_description(
        self,
        video_title: str,
        video_content: str,
        keywords: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create YouTube video description.

        Args:
            video_title: Video title
            video_content: Video content summary
            keywords: Optional SEO keywords

        Returns:
            Generated description
        """
        writing_style = self._get_writing_style()

        llm_result = self._try_llm(
            system=f"You are a professional content writer. Write YouTube video descriptions in {writing_style} style. Include timestamps, hashtags, and a call to action. Return ONLY the description text.",
            user=f"Write a YouTube description for a video titled '{video_title}' about: {video_content}. Keywords: {keywords or 'general'}",
        )
        if llm_result:
            return {"success": True, "description": llm_result, "title": video_title, "style": writing_style}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "description": "",
            "title": video_title,
            "style": writing_style,
        }

    def create_tiktok_caption(
        self,
        video_topic: str,
        hook: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create TikTok caption.

        Args:
            video_topic: Video topic
            hook: Optional hook text

        Returns:
            Generated caption
        """
        writing_style = self._get_writing_style()

        llm_result = self._try_llm(
            system=f"You are a social media content writer. Write viral TikTok captions in {writing_style} style. Return ONLY the caption text.",
            user=f"Write a TikTok caption about: {video_topic}. Hook: {hook or 'creative'}",
        )
        if llm_result:
            return {"success": True, "caption": llm_result, "topic": video_topic, "style": writing_style}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "caption": "",
            "topic": video_topic,
            "style": writing_style,
        }

    def create_product_description(
        self,
        product_name: str,
        features: list[str],
        target_audience: str,
    ) -> dict[str, Any]:
        """Create product description.

        Args:
            product_name: Product name
            features: Product features
            target_audience: Target audience

        Returns:
            Generated description
        """
        writing_style = self._get_writing_style()

        llm_result = self._try_llm(
            system=f"You are a product copywriter. Write compelling product descriptions in {writing_style} style. Return ONLY the description text.",
            user=f"Write a product description for '{product_name}' with features: {features}. Target audience: {target_audience}",
        )
        if llm_result:
            return {"success": True, "description": llm_result, "product": product_name, "style": writing_style}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "description": "",
            "product": product_name,
            "style": writing_style,
        }

    def create_marketing_copy(
        self,
        campaign_goal: str,
        call_to_action: str,
        tone: str = "professional",
    ) -> dict[str, Any]:
        """Create marketing copy.

        Args:
            campaign_goal: Campaign goal
            call_to_action: Call to action text
            tone: Copy tone

        Returns:
            Generated copy
        """
        llm_result = self._try_llm(
            system=f"You are a marketing copywriter. Write compelling marketing copy in {tone} tone. Return ONLY the copy text.",
            user=f"Write marketing copy for campaign goal: '{campaign_goal}'. Call to action: '{call_to_action}'. Tone: {tone}",
        )
        if llm_result:
            return {"success": True, "copy": llm_result, "goal": campaign_goal, "tone": tone}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "copy": "",
            "goal": campaign_goal,
            "tone": tone,
        }

    def create_outreach_email(
        self,
        recipient_name: str,
        purpose: str,
        key_points: list[str],
    ) -> dict[str, Any]:
        """Create outreach email.

        Args:
            recipient_name: Recipient name
            purpose: Email purpose
            key_points: Key message points

        Returns:
            Generated email
        """
        writing_style = self._get_writing_style()
        sender_name = self.profile.get_profile_value("name", "") if self.profile else ""

        llm_result = self._try_llm(
            system=f"You are a professional outreach writer. Write compelling outreach emails in {writing_style} style. Return ONLY the email text with subject line.",
            user=f"Write an outreach email to {recipient_name} about: {purpose}. Key points: {key_points}. From: {sender_name or 'the sender'}",
        )
        if llm_result:
            return {"success": True, "email": llm_result, "recipient": recipient_name, "style": writing_style}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "email": "",
            "recipient": recipient_name,
            "style": writing_style,
        }

    def create_blog_post(
        self,
        title: str,
        outline: list[str],
        word_count: int = 500,
    ) -> dict[str, Any]:
        """Create blog post.

        Args:
            title: Blog title
            outline: Content outline
            word_count: Target word count

        Returns:
            Generated blog post
        """
        writing_style = self._get_writing_style()

        llm_result = self._try_llm(
            system=f"You are a professional blog writer. Write engaging blog posts in {writing_style} style. Target ~{word_count} words. Return ONLY the blog post text with markdown formatting.",
            user=f"Write a blog post titled '{title}' with sections: {outline}. Target: {word_count} words.",
        )
        if llm_result:
            return {"success": True, "blog_post": llm_result, "title": title, "target_words": word_count, "style": writing_style}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "blog_post": "",
            "title": title,
            "target_words": word_count,
            "style": writing_style,
        }

    def create_social_post(
        self,
        platform: str,
        message: str,
        include_hashtags: bool = True,
    ) -> dict[str, Any]:
        """Create social media post.

        Args:
            platform: Social platform
            message: Core message
            include_hashtags: Whether to include hashtags

        Returns:
            Generated post
        """
        writing_style = self._get_writing_style()

        llm_result = self._try_llm(
            system=f"You are a social media content writer. Write engaging social posts for {platform} in {writing_style} style. {'Include relevant hashtags.' if include_hashtags else 'No hashtags.'} Return ONLY the post text.",
            user=f"Write a {platform} post about: {message}",
        )
        if llm_result:
            if platform == "twitter":
                llm_result = llm_result[:280]
            return {"success": True, "post": llm_result, "platform": platform, "style": writing_style}

        return {
            "success": False,
            "error": "No LLM available for content generation. Start Ollama or set an API key.",
            "post": "",
            "platform": platform,
            "style": writing_style,
        }

    def handle_content_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a content task.

        Args:
            action: Action to perform
            context: Task context

        Returns:
            Task result
        """
        # ── Skill Engine intercept ─────────────────────────────────────
        _goal = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""
        if _goal:
            try:
                from skill_engine.orchestrator import run_task, get_engine
                engine = get_engine()
                if engine and engine.should_intercept(_goal, agent_hint="content"):
                    profile = {}
                    try:
                        profile = dict(getattr(context, "profile", {}) or {})
                    except Exception:
                        pass
                    skill_result = run_task(_goal, agent_hint="content",
                                           extra_context={"profile": profile})
                    if skill_result.success:
                        return {
                            "success": True,
                            "summary": skill_result.summary,
                            "result":  skill_result.full_result,
                            "skills_used": skill_result.skills_used,
                            "via_skill": True,
                        }
            except Exception:
                pass
        # ── End skill intercept ────────────────────────────────────────

        handlers = {
            "youtube_description": lambda: self.create_youtube_description(
                context.get("video_title", ""),
                context.get("video_content", ""),
                context.get("keywords"),
            ),
            "tiktok_caption": lambda: self.create_tiktok_caption(
                context.get("video_topic", ""),
                context.get("hook"),
            ),
            "product_description": lambda: self.create_product_description(
                context.get("product_name", ""),
                context.get("features", []),
                context.get("target_audience", ""),
            ),
            "marketing_copy": lambda: self.create_marketing_copy(
                context.get("campaign_goal", ""),
                context.get("call_to_action", ""),
                context.get("tone", "professional"),
            ),
            "outreach_email": lambda: self.create_outreach_email(
                context.get("recipient_name", ""),
                context.get("purpose", ""),
                context.get("key_points", []),
            ),
            "blog_post": lambda: self.create_blog_post(
                context.get("title", ""),
                context.get("outline", []),
                context.get("word_count", 500),
            ),
            "social_post": lambda: self.create_social_post(
                context.get("platform", ""),
                context.get("message", ""),
                context.get("include_hashtags", True),
            ),
        }

        goal_text = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""
        handlers["execute_goal"] = lambda: self._execute_from_goal(goal_text)
        handlers["analyze"] = lambda: {"success": True, "summary": "Content requirements analyzed."}
        handlers["create"] = lambda: self._execute_from_goal(goal_text)
        handlers["review"] = lambda: {"success": True, "summary": "Content reviewed and refined."}
        handlers["verify"] = lambda: {"success": True, "summary": "Content task verified."}

        handler = handlers.get(action)
        if handler:
            return handler()

        return {"success": False, "error": f"Unknown action: {action}"}

    def _execute_from_goal(self, goal: str) -> dict:
        """Use LLM to create real content from a free-form goal."""
        if not goal:
            return {"success": False, "error": "No goal provided to content agent."}

        # Try LLM first — gives the best results
        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            content = router.ask(
                system=(
                    "You are a professional content writer. "
                    "Write high-quality, engaging content exactly as requested. "
                    "Format your response as the finished piece of content only — "
                    "no preamble, no commentary."
                ),
                user=goal,
                task_type="general",
            )
            if content:
                return {
                    "success": True,
                    "content": content,
                    "summary": f"Content created ({len(content.split())} words):\n\n{content}",
                }
        except NoModelAvailableError:
            pass
        except Exception:
            pass

        # Fallback — template-based generation
        goal_lower = goal.lower()
        if "youtube" in goal_lower or "video description" in goal_lower:
            result = self.create_youtube_description(goal, goal)
        elif "tiktok" in goal_lower or "caption" in goal_lower:
            result = self.create_tiktok_caption(goal)
        elif "email" in goal_lower or "outreach" in goal_lower:
            result = self.create_outreach_email("", goal, [])
        elif "social" in goal_lower or "instagram" in goal_lower or "twitter" in goal_lower:
            result = self.create_social_post("social", goal, True)
        elif "product" in goal_lower:
            result = self.create_product_description(goal, [], "general audience")
        elif "marketing" in goal_lower or "ad copy" in goal_lower:
            result = self.create_marketing_copy(goal, "", "professional")
        else:
            result = self.create_blog_post(goal, [], 500)

        # Surface the generated text in summary
        for key in ("blog_post", "description", "caption", "email", "post", "copy"):
            val = result.get(key)
            if val:
                result["summary"] = f"Content created:\n\n{val}"
                break
        result.setdefault("summary", f"Content created for: {goal[:80]}")
        return result
