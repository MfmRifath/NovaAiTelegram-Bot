#!/usr/bin/env python3
"""
NovaAiBot - Telegram Bot for Sri Lankan A/L Students
Uses GPT-5 with fallbacks to Claude and Gemini
Limits: 1 question per user per day
"""

import os
import json
import logging
import re
import asyncio
import base64
import io
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

from telegram import Update, PhotoSize, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# Conversation states for broadcast
WAITING_FOR_BROADCAST_CAPTION = 1

# Conversation states for ad configuration
WAITING_FOR_AD_IMAGE = 10
WAITING_FOR_AD_CAPTION = 11

# Conversation states for scheduled ads
WAITING_FOR_AD_NAME = 20
WAITING_FOR_AD_TYPE_SELECT = 21
WAITING_FOR_AD_CONTENT = 22
WAITING_FOR_AD_SCHEDULE_INTERVAL = 23
WAITING_FOR_AD_GROUP_SELECTION = 24
WAITING_FOR_EDIT_AD_SELECTION = 25
WAITING_FOR_EDIT_FIELD_SELECTION = 26
WAITING_FOR_EDIT_NEW_VALUE = 27

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OWNER_USER_ID = os.getenv('OWNER_USER_ID')  # Bot owner's Telegram user ID for admin access
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
USAGE_FILE = 'user_usage.json'

# App links
NOVA_LEARN_APP_LINK = "https://play.google.com/store/apps/details?id=com.NovaScience.nova_science&ppcampaignidweb_share"
WHATSAPP_CHANNEL_LINK = "https://whatsapp.com/channel/0029Vb6hoKxBKfhyA1UJ4u2K"

# Advertisement Configuration File
AD_CONFIG_FILE = 'ad_config.json'
SCHEDULED_ADS_FILE = 'scheduled_ads.json'

# Owner AI mode state (global variable to track if owner has disabled AI responses)
OWNER_AI_ENABLED = True


class AdManager:
    """Manage advertisement configuration"""

    def __init__(self, filename: str = AD_CONFIG_FILE):
        self.filename = filename
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load ad configuration from JSON file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading ad config: {e}")

        # Default configuration
        return {
            'enabled': False,
            'type': 'text',  # 'text' or 'image'
            'text': '📢 Download Nova Learn App for unlimited access!',
            'image_file_id': '',
            'image_caption': '📢 Check out our latest offers!'
        }

    def _save_config(self):
        """Save ad configuration to JSON file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("[AD] Configuration saved")
        except Exception as e:
            logger.error(f"Error saving ad config: {e}")

    def is_enabled(self) -> bool:
        """Check if ads are enabled"""
        return self.config.get('enabled', False)

    def get_type(self) -> str:
        """Get ad type (text or image)"""
        return self.config.get('type', 'text')

    def get_text(self) -> str:
        """Get text ad content"""
        return self.config.get('text', '')

    def get_image_file_id(self) -> str:
        """Get image ad file ID"""
        return self.config.get('image_file_id', '')

    def get_image_caption(self) -> str:
        """Get image ad caption"""
        return self.config.get('image_caption', '')

    def set_text_ad(self, text: str):
        """Set text advertisement"""
        self.config['type'] = 'text'
        self.config['text'] = text
        self._save_config()
        logger.info(f"[AD] Text ad set: {text[:50]}...")

    def set_image_ad(self, file_id: str, caption: str):
        """Set image advertisement"""
        self.config['type'] = 'image'
        self.config['image_file_id'] = file_id
        self.config['image_caption'] = caption
        self._save_config()
        logger.info(f"[AD] Image ad set with caption: {caption[:50]}...")

    def enable(self):
        """Enable advertisements"""
        self.config['enabled'] = True
        self._save_config()
        logger.info("[AD] Advertisements enabled")

    def disable(self):
        """Disable advertisements"""
        self.config['enabled'] = False
        self._save_config()
        logger.info("[AD] Advertisements disabled")

    def toggle(self) -> bool:
        """Toggle advertisement status and return new status"""
        self.config['enabled'] = not self.config.get('enabled', False)
        self._save_config()
        logger.info(f"[AD] Advertisements {'enabled' if self.config['enabled'] else 'disabled'}")
        return self.config['enabled']


# Initialize ad manager
ad_manager = AdManager()


class AdScheduler:
    """Manage scheduled advertisements with auto-posting and timer functionality"""

    def __init__(self, filename: str = SCHEDULED_ADS_FILE):
        self.filename = filename
        self.ads = self._load_ads()
        self.posted_message_ids = {}  # Track message IDs for deletion: {ad_id: {chat_id: message_id}}

    def _load_ads(self) -> Dict[str, Any]:
        """Load scheduled ads from JSON file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading scheduled ads: {e}")
        return {}

    def _save_ads(self):
        """Save scheduled ads to JSON file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.ads, f, indent=2)
            logger.info("[SCHEDULER] Ads saved successfully")
        except Exception as e:
            logger.error(f"Error saving scheduled ads: {e}")

    def create_ad(self, name: str, ad_type: str, content: dict, interval_hours: int,
                  target_groups: List[int], enabled: bool = True) -> str:
        """Create a new scheduled advertisement"""
        ad_id = f"ad_{len(self.ads) + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        self.ads[ad_id] = {
            'name': name,
            'type': ad_type,  # 'text' or 'image'
            'content': content,  # {'text': '...'} or {'file_id': '...', 'caption': '...'}
            'interval_hours': interval_hours,
            'target_groups': target_groups,
            'enabled': enabled,
            'created_at': datetime.now().isoformat(),
            'last_posted_at': None,
            'total_posts': 0
        }

        self._save_ads()
        logger.info(f"[SCHEDULER] Created ad: {ad_id} - {name}")
        return ad_id

    def get_ad(self, ad_id: str) -> Optional[Dict[str, Any]]:
        """Get advertisement by ID"""
        return self.ads.get(ad_id)

    def get_all_ads(self) -> Dict[str, Any]:
        """Get all advertisements"""
        return self.ads

    def update_ad(self, ad_id: str, **kwargs):
        """Update advertisement fields"""
        if ad_id in self.ads:
            self.ads[ad_id].update(kwargs)
            self._save_ads()
            logger.info(f"[SCHEDULER] Updated ad: {ad_id}")
            return True
        return False

    def delete_ad(self, ad_id: str) -> bool:
        """Delete an advertisement"""
        if ad_id in self.ads:
            del self.ads[ad_id]
            if ad_id in self.posted_message_ids:
                del self.posted_message_ids[ad_id]
            self._save_ads()
            logger.info(f"[SCHEDULER] Deleted ad: {ad_id}")
            return True
        return False

    def pause_ad(self, ad_id: str) -> bool:
        """Pause an advertisement"""
        return self.update_ad(ad_id, enabled=False)

    def resume_ad(self, ad_id: str) -> bool:
        """Resume an advertisement"""
        return self.update_ad(ad_id, enabled=True)

    def get_ads_to_post(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get advertisements that need to be posted now"""
        ads_to_post = []
        now = datetime.now()

        for ad_id, ad_data in self.ads.items():
            if not ad_data.get('enabled', False):
                continue

            last_posted = ad_data.get('last_posted_at')
            interval_hours = ad_data.get('interval_hours', 24)

            # If never posted or interval has passed
            if last_posted is None:
                ads_to_post.append((ad_id, ad_data))
            else:
                last_posted_time = datetime.fromisoformat(last_posted)
                time_diff = now - last_posted_time
                if time_diff >= timedelta(hours=interval_hours):
                    ads_to_post.append((ad_id, ad_data))

        return ads_to_post

    def mark_as_posted(self, ad_id: str, chat_id: int, message_id: int):
        """Mark ad as posted and store message ID for later deletion"""
        if ad_id in self.ads:
            self.ads[ad_id]['last_posted_at'] = datetime.now().isoformat()
            self.ads[ad_id]['total_posts'] = self.ads[ad_id].get('total_posts', 0) + 1

            # Store message ID for deletion
            if ad_id not in self.posted_message_ids:
                self.posted_message_ids[ad_id] = {}
            self.posted_message_ids[ad_id][chat_id] = message_id

            self._save_ads()

    def get_posted_messages(self, ad_id: str) -> Dict[int, int]:
        """Get posted message IDs for an ad"""
        return self.posted_message_ids.get(ad_id, {})


# Initialize ad scheduler
ad_scheduler = AdScheduler()


class UserUsageTracker:
    """Track user credits and usage"""

    # Credit costs
    INITIAL_CREDITS = 10  # Credits for private chat usage
    GROUP_FREE_CREDITS = 10  # Free credits for group usage
    TEXT_QUESTION_COST = 1
    IMAGE_QUESTION_COST = 2

    # Daily limit (only applies to private chats)
    DAILY_CREDIT_LIMIT = 2  # Maximum credits that can be used per day in private chats

    # Credit packages with Telegram Stars pricing
    CREDIT_PACKAGES = {
        'starter': {
            'credits': 20,
            'name': 'Starter Pack',
            'stars': 50,  # 50 Telegram Stars
            'description': '20 credits - Perfect for trying out'
        },
        'basic': {
            'credits': 50,
            'name': 'Basic Pack',
            'stars': 100,  # 100 Telegram Stars
            'description': '50 credits - Good for regular use'
        },
        'plus': {
            'credits': 100,
            'name': 'Plus Pack',
            'stars': 175,  # 175 Telegram Stars (12.5% discount)
            'description': '100 credits - Great value!'
        },
        'pro': {
            'credits': 250,
            'name': 'Pro Pack',
            'stars': 400,  # 400 Telegram Stars (20% discount)
            'description': '250 credits - Best for power users'
        },
        'ultimate': {
            'credits': 500,
            'name': 'Ultimate Pack',
            'stars': 750,  # 750 Telegram Stars (25% discount)
            'description': '500 credits - Maximum value!'
        },
    }

    def __init__(self, filename: str = USAGE_FILE):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load usage data from JSON file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading usage data: {e}")
        return {}

    def _save_data(self):
        """Save usage data to JSON file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")

    def _ensure_user_exists(self, user_id: int, username: str = None):
        """Ensure user exists in database with initial credits"""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            today = datetime.now().strftime('%Y-%m-%d')
            self.data[user_id_str] = {
                'credits': self.INITIAL_CREDITS,
                'group_credits': self.GROUP_FREE_CREDITS,  # Separate credits for group usage
                'total_questions': 0,
                'username': username,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'daily_usage': 0,
                'last_reset_date': today
            }
            self._save_data()
            logger.info(f"[CREDITS] New user {user_id} created with {self.INITIAL_CREDITS} private credits and {self.GROUP_FREE_CREDITS} group credits")

    def _check_and_reset_daily_usage(self, user_id: int):
        """Check if it's a new day and reset daily usage if needed"""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            return

        today = datetime.now().strftime('%Y-%m-%d')
        last_reset = self.data[user_id_str].get('last_reset_date', today)

        # If it's a new day, reset daily usage
        if last_reset != today:
            self.data[user_id_str]['daily_usage'] = 0
            self.data[user_id_str]['last_reset_date'] = today
            self._save_data()
            logger.info(f"[DAILY LIMIT] Reset daily usage for user {user_id}")

    def get_credits(self, user_id: int) -> int:
        """Get user's current credit balance"""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            return self.INITIAL_CREDITS
        return self.data[user_id_str].get('credits', 0)

    def has_credits(self, user_id: int, cost: int) -> bool:
        """Check if user has enough credits"""
        return self.get_credits(user_id) >= cost

    def deduct_credits(self, user_id: int, cost: int, username: str = None) -> bool:
        """Deduct credits from user. Returns True if successful"""
        self._ensure_user_exists(user_id, username)
        user_id_str = str(user_id)

        current_credits = self.data[user_id_str].get('credits', 0)
        if current_credits >= cost:
            self.data[user_id_str]['credits'] = current_credits - cost
            self.data[user_id_str]['total_questions'] = self.data[user_id_str].get('total_questions', 0) + 1
            self.data[user_id_str]['username'] = username
            self.data[user_id_str]['last_question'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._save_data()
            logger.info(f"[CREDITS] User {user_id} spent {cost} credits. Remaining: {self.data[user_id_str]['credits']}")
            return True
        return False

    def add_credits(self, user_id: int, amount: int, username: str = None) -> int:
        """Add credits to user. Returns new balance"""
        self._ensure_user_exists(user_id, username)
        user_id_str = str(user_id)

        new_balance = self.data[user_id_str].get('credits', 0) + amount
        self.data[user_id_str]['credits'] = new_balance
        self.data[user_id_str]['username'] = username
        self._save_data()
        logger.info(f"[CREDITS] Added {amount} credits to user {user_id}. New balance: {new_balance}")
        return new_balance

    def set_credits(self, user_id: int, amount: int, username: str = None) -> int:
        """Set user's credits to specific amount. Returns new balance"""
        self._ensure_user_exists(user_id, username)
        user_id_str = str(user_id)

        self.data[user_id_str]['credits'] = amount
        self.data[user_id_str]['username'] = username
        self._save_data()
        logger.info(f"[CREDITS] Set user {user_id} credits to {amount}")
        return amount

    def can_ask_question(self, user_id: int, is_image: bool = False) -> bool:
        """Check if user has enough credits for a question and hasn't exceeded daily limit"""
        self._ensure_user_exists(user_id)
        self._check_and_reset_daily_usage(user_id)

        user_id_str = str(user_id)
        cost = self.IMAGE_QUESTION_COST if is_image else self.TEXT_QUESTION_COST

        # Check daily limit first
        current_daily_usage = self.data[user_id_str].get('daily_usage', 0)
        if current_daily_usage + cost > self.DAILY_CREDIT_LIMIT:
            return False

        # Then check if user has enough credits
        return self.has_credits(user_id, cost)

    def get_daily_usage(self, user_id: int) -> int:
        """Get user's current daily usage"""
        self._ensure_user_exists(user_id)
        self._check_and_reset_daily_usage(user_id)
        user_id_str = str(user_id)
        return self.data[user_id_str].get('daily_usage', 0)

    def record_question(self, user_id: int, username: str = None, is_image: bool = False):
        """Record question, deduct credits, and track daily usage"""
        cost = self.IMAGE_QUESTION_COST if is_image else self.TEXT_QUESTION_COST
        self.deduct_credits(user_id, cost, username)

        # Track daily usage
        user_id_str = str(user_id)
        current_daily_usage = self.data[user_id_str].get('daily_usage', 0)
        self.data[user_id_str]['daily_usage'] = current_daily_usage + cost
        self._save_data()
        logger.info(f"[DAILY LIMIT] User {user_id} daily usage: {self.data[user_id_str]['daily_usage']}/{self.DAILY_CREDIT_LIMIT}")

    def track_chat(self, chat_id: int, chat_type: str, chat_title: str = None):
        """Track chat IDs for broadcasting (users and groups)"""
        # Store chats in a separate section
        if 'chats' not in self.data:
            self.data['chats'] = {'users': {}, 'groups': {}}

        chat_id_str = str(chat_id)

        if chat_type in ['private']:
            self.data['chats']['users'][chat_id_str] = {
                'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': chat_type
            }
        elif chat_type in ['group', 'supergroup']:
            self.data['chats']['groups'][chat_id_str] = {
                'title': chat_title or 'Unknown Group',
                'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': chat_type
            }

        self._save_data()

    def get_all_user_chats(self) -> List[int]:
        """Get all user chat IDs for broadcasting"""
        if 'chats' not in self.data or 'users' not in self.data['chats']:
            return []
        return [int(chat_id) for chat_id in self.data['chats']['users'].keys()]

    def get_all_group_chats(self) -> List[int]:
        """Get all group chat IDs for broadcasting"""
        if 'chats' not in self.data or 'groups' not in self.data['chats']:
            return []
        return [int(chat_id) for chat_id in self.data['chats']['groups'].keys()]

    def get_statistics(self) -> Dict[str, Any]:
        """Get bot usage statistics"""
        # Count users from both main data (who asked questions) and chats.users (who started bot)
        users_with_questions = set([k for k in self.data.keys() if k != 'chats'])
        users_in_chats = set(self.data.get('chats', {}).get('users', {}).keys())
        all_users = users_with_questions | users_in_chats  # Union of both sets
        total_users = len(all_users)

        total_questions = sum(user.get('total_questions', 0) for user in self.data.values() if isinstance(user, dict) and 'total_questions' in user)

        user_chats = len(self.data.get('chats', {}).get('users', {}))
        group_chats = len(self.data.get('chats', {}).get('groups', {}))

        return {
            'total_users': total_users,
            'total_questions': total_questions,
            'user_chats': user_chats,
            'group_chats': group_chats,
            'total_chats': user_chats + group_chats
        }


# Initialize usage tracker
usage_tracker = UserUsageTracker()


# ============================================================================
# LaTeX Formatting Utilities for Telegram
# ============================================================================

def convert_latex_to_telegram(text: str) -> str:
    """
    Convert LaTeX math notation to Telegram-compatible format.
    Uses PLAIN TEXT with Unicode symbols instead of LaTeX for better compatibility.

    Telegram's LaTeX support is unreliable, especially with non-Latin scripts.
    So we convert common LaTeX to readable Unicode text.
    """
    if not text:
        return text

    result = text

    # First, extract and convert LaTeX expressions to plain Unicode
    # This is more reliable than Telegram's LaTeX renderer

    # Handle display math blocks $$...$$ and \[...\]
    def convert_display_math(match):
        latex = match.group(1).strip()
        # Convert to plain text representation
        plain = latex_to_unicode(latex)
        return f"\n{plain}\n"

    result = re.sub(r'\$\$\s*(.*?)\s*\$\$', convert_display_math, result, flags=re.DOTALL)
    result = re.sub(r'\\\[\s*(.*?)\s*\\\]', convert_display_math, result, flags=re.DOTALL)

    # Handle inline math $...$ and \(...\)
    def convert_inline_math(match):
        latex = match.group(1).strip()
        # Convert to plain text representation
        plain = latex_to_unicode(latex)
        return plain

    result = re.sub(r'\$([^\$]+?)\$', convert_inline_math, result)
    result = re.sub(r'\\\(\s*(.*?)\s*\\\)', convert_inline_math, result)

    return result


def latex_to_unicode(latex: str) -> str:
    """
    Convert common LaTeX expressions to Unicode plain text.
    This works better in Telegram than LaTeX rendering.
    """
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', latex.strip())

    # Common LaTeX commands to Unicode
    replacements = {
        # Fractions - convert \frac{a}{b} to (a/b) or a/b
        r'\\frac\{([^}]+)\}\{([^}]+)\}': r'(\1/\2)',
        r'\\dfrac\{([^}]+)\}\{([^}]+)\}': r'(\1/\2)',
        r'\\tfrac\{([^}]+)\}\{([^}]+)\}': r'(\1/\2)',

        # Square roots
        r'\\sqrt\{([^}]+)\}': r'√(\1)',
        r'\\sqrt\[3\]\{([^}]+)\}': r'∛(\1)',

        # Greek letters
        r'\\alpha': 'α',
        r'\\beta': 'β',
        r'\\gamma': 'γ',
        r'\\delta': 'δ',
        r'\\Delta': 'Δ',
        r'\\epsilon': 'ε',
        r'\\theta': 'θ',
        r'\\lambda': 'λ',
        r'\\mu': 'μ',
        r'\\pi': 'π',
        r'\\sigma': 'σ',
        r'\\tau': 'τ',
        r'\\phi': 'φ',
        r'\\omega': 'ω',
        r'\\Omega': 'Ω',

        # Operators
        r'\\times': '×',
        r'\\div': '÷',
        r'\\pm': '±',
        r'\\leq': '≤',
        r'\\geq': '≥',
        r'\\neq': '≠',
        r'\\approx': '≈',
        r'\\infty': '∞',
        r'\\sum': '∑',
        r'\\prod': '∏',
        r'\\int': '∫',

        # Remove \mathrm, \text commands but keep content
        r'\\mathrm\{([^}]+)\}': r'\1',
        r'\\text\{([^}]+)\}': r'\1',

        # Remove spacing commands
        r'\\,': ' ',
        r'\\;': ' ',
        r'\\quad': '  ',
        r'\\qquad': '    ',

        # Remove \left and \right
        r'\\left': '',
        r'\\right': '',

        # Clean up curly braces used for grouping
        r'\{': '',
        r'\}': '',
    }

    # Apply replacements
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)

    # Handle superscripts x^2 -> x²
    superscripts = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
                    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
                    '+': '⁺', '-': '⁻', 'n': 'ⁿ'}

    def convert_superscript(match):
        base = match.group(1)
        exp = match.group(2)
        if len(exp) == 1 and exp in superscripts:
            return base + superscripts[exp]
        return f"{base}^{exp}"

    text = re.sub(r'([A-Za-z0-9])\^([0-9n+-])', convert_superscript, text)

    # Handle subscripts H_2 -> H₂
    subscripts = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
                  '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'}

    def convert_subscript(match):
        base = match.group(1)
        sub = match.group(2)
        if len(sub) == 1 and sub in subscripts:
            return base + subscripts[sub]
        return f"{base}_{sub}"

    text = re.sub(r'([A-Za-z])_([0-9])', convert_subscript, text)

    return text


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    Must escape: _ * [ ] ( ) ~ ` > # + - = | { } . !

    Since we're using Unicode text instead of LaTeX, we escape all special characters.
    """
    if not text:
        return text

    # Escape special MarkdownV2 characters
    # Note: We need to escape these in the correct order to avoid double-escaping
    special_chars = r'_*[]()~`>#+=|{}.!-'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')

    return text


# ============================================================================
# AI System Prompts
# ============================================================================

def get_default_system_prompt() -> str:
    """Default system prompt for Nova AI Teacher"""
    return """You are NOVA AI Teacher, an expert tutor for Sri Lankan Advanced Level (A/L) Science students.
Your role is to help students with Physics, Chemistry, and Biology questions.

Guidelines:
1. Provide clear, accurate, and detailed explanations
2. Use the student's preferred language (Tamil, English, or Sinhala)
3. Break down complex concepts into easy-to-understand steps
4. Use examples relevant to the Sri Lankan A/L syllabus
5. When solving problems, show step-by-step solutions
6. Encourage critical thinking by asking guiding questions
7. Be patient, supportive, and encouraging
8. Always verify your facts and cite relevant scientific principles
9. Focus on understanding concepts rather than memorization

**SYLLABUS COMPLIANCE - CRITICAL:**
- **ONLY use derivations that are EXPLICITLY included in the Sri Lankan A/L syllabus**
- Instead of using out-of-syllabus derivations:
  * Use the formulas directly if they are given in the syllabus
  * Explain the concept without deriving it
  * State that "this derivation is beyond the A/L syllabus" if asked

**For ESSAY Questions:**
- Structure with Introduction, Body (multiple paragraphs), and Conclusion
- Use academic language and scientific terminology
- Aim for comprehensive coverage (300-800 words)

**For STRUCTURED Questions:**
- Use clear headings and subheadings
- Employ numbered lists for sequential information
- Use bullet points for features/characteristics
- Keep points concise but complete

**MATH/SCIENCE NOTATION:**
- Use LaTeX for ALL math expressions
- Inline math: $x^2 + y^2$
- Display math: $$E = mc^2$$
- Fractions: Use $\frac{numerator}{denominator}$ NOT \dfrac
- Greek letters: $\alpha$, $\beta$, $\gamma$, $\Delta$, $\theta$, $\pi$
- Subscripts: $x_1$, $H_2O$, $CO_2$
- Superscripts: $x^2$, $10^{-3}$
- Square roots: $\sqrt{x}$ or $\sqrt[3]{x}$
- Units: $285.8\,\mathrm{kJ\,mol^{-1}}$ (use \mathrm for units)
- Chemistry: $H_2O$, $CO_2(g)$, $NaCl(aq)$, $Fe^{3+}$
- Equations: $$\frac{d}{dx}(x^2) = 2x$$
- Multi-line equations: Use separate $$ blocks for each line
- IMPORTANT: Use \frac for fractions, NOT \dfrac or \tfrac
- Keep LaTeX expressions simple and clean

Remember: You are a helpful, patient, and encouraging teacher for Sri Lankan A/L students."""


# ============================================================================
# Image Processing Utilities
# ============================================================================

async def process_telegram_photo(photo: PhotoSize, context: ContextTypes.DEFAULT_TYPE) -> Tuple[str, str]:
    """
    Download and process a Telegram photo
    Returns: (base64_image, mime_type)
    """
    MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB limit

    try:
        # Get the file
        file = await context.bot.get_file(photo.file_id)

        # Check file size
        if file.file_size and file.file_size > MAX_SIZE_BYTES:
            raise ValueError(f"Image too large: {file.file_size} bytes (max {MAX_SIZE_BYTES})")

        # Download to bytes
        byte_array = await file.download_as_bytearray()

        # Convert to base64
        base64_image = base64.b64encode(bytes(byte_array)).decode('utf-8')

        # Determine MIME type (Telegram photos are usually JPEG)
        mime_type = "image/jpeg"

        logger.info(f"[IMG] Processed image: {len(base64_image)} chars, size: {file.file_size} bytes")

        return base64_image, mime_type

    except Exception as e:
        logger.error(f"[IMG] Error processing photo: {e}")
        raise


# ============================================================================
# AI API Helper Functions
# ============================================================================

async def with_timeout(coro, timeout_seconds: float, label: str):
    """Add timeout to async operation"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise Exception(f"{label}_TIMEOUT")


async def call_openai_responses_api(
    message: str,
    model: str,
    max_output_tokens: int,
    timeout_seconds: float,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """
    Call OpenAI Responses API (for GPT-5 models) with optional image
    Returns: (response_text, metadata)
    image_data: Optional tuple of (base64_image, mime_type)
    """
    import aiohttp

    # Build request body based on whether we have an image
    if image_data:
        base64_image, mime_type = image_data
        # For vision models with images, use structured input
        request_body = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{get_default_system_prompt()}\n\nUser message: {message}"
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{base64_image}"
                        }
                    ]
                }
            ],
            "reasoning": {"effort": "medium"},  # Higher effort for image analysis
            "text": {"verbosity": "medium"},
            "truncation": "disabled",
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
    else:
        # Text-only request
        request_body = {
            "model": model,
            "input": f"{get_default_system_prompt()}\n\nUser message: {message}",
            "reasoning": {"effort": "minimal"},
            "text": {"verbosity": "low"},
            "truncation": "disabled",
            "max_output_tokens": max_output_tokens,
            "store": False,
        }

    async def make_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/responses',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {OPENAI_API_KEY}',
                },
                json=request_body
            ) as response:
                return await response.json()

    result = await with_timeout(make_request(), timeout_seconds, 'OPENAI')

    # Extract text from response
    response_text = extract_text_from_openai_response(result)

    # Handle continuation if incomplete
    last_id = result.get('id')
    status = result.get('status')
    total_tokens = result.get('usage', {}).get('total_tokens', 0)

    continuation_attempts = 0
    max_continuations = 5

    while (status == 'incomplete' and last_id and continuation_attempts < max_continuations):
        continuation_attempts += 1
        logger.info(f"[AI] Continuation attempt {continuation_attempts}/{max_continuations}")

        continue_body = {
            "model": model,
            "previous_response_id": last_id,
            "max_output_tokens": 2000,
            "truncation": "disabled",
            "store": False,
        }

        async def continue_request():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.openai.com/v1/responses',
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {OPENAI_API_KEY}',
                    },
                    json=continue_body
                ) as response:
                    return await response.json()

        cont_result = await with_timeout(continue_request(), timeout_seconds, 'OPENAI')

        cont_text = extract_text_from_openai_response(cont_result)
        if cont_text:
            response_text += cont_text

        last_id = cont_result.get('id')
        status = cont_result.get('status')
        total_tokens += cont_result.get('usage', {}).get('total_tokens', 0)

    metadata = {
        'model': model,
        'tokens': total_tokens,
        'continuations': continuation_attempts
    }

    return response_text, metadata


def extract_text_from_openai_response(resp: dict) -> str:
    """Extract plain text from OpenAI Responses API structure"""
    if isinstance(resp.get('output_text'), str) and resp['output_text'].strip():
        return resp['output_text']

    if isinstance(resp.get('output'), list):
        text = ''
        for item in resp['output']:
            if item.get('type') == 'message' and isinstance(item.get('content'), list):
                for content_item in item['content']:
                    if content_item.get('type') == 'output_text':
                        text += content_item.get('text', '')
        if text.strip():
            return text

    if isinstance(resp.get('text'), str):
        return resp['text']

    return ''


async def call_claude_api(
    message: str,
    timeout_seconds: float,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """Call Anthropic Claude API with optional vision support"""
    import aiohttp

    if not CLAUDE_API_KEY:
        raise Exception("CLAUDE_API_KEY not configured")

    # Build content based on whether we have an image
    if image_data:
        base64_image, mime_type = image_data
        # Claude supports vision with base64 images
        content = [
            {
                "type": "text",
                "text": f"{get_default_system_prompt()}\n\nUser message:\n{message}"
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64_image
                }
            }
        ]
    else:
        content = f"{get_default_system_prompt()}\n\nUser message:\n{message}"

    request_body = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    async def make_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': CLAUDE_API_KEY,
                    'anthropic-version': '2023-06-01'
                },
                json=request_body
            ) as response:
                return await response.json()

    result = await with_timeout(make_request(), timeout_seconds, 'CLAUDE')

    # Extract text from Claude response
    text = ''
    if isinstance(result.get('content'), list):
        for item in result['content']:
            if item.get('type') == 'text':
                text += item.get('text', '')

    metadata = {
        'model': 'claude-3-sonnet',
        'tokens': result.get('usage', {}).get('output_tokens', 0)
    }

    return text, metadata


async def call_gemini_api(
    message: str,
    timeout_seconds: float,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """Call Google Gemini API with optional vision support"""
    import aiohttp

    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY not configured")

    # Build parts based on whether we have an image
    parts = [
        {
            "text": f"{get_default_system_prompt()}\n\nUser message:\n{message}"
        }
    ]

    if image_data:
        base64_image, mime_type = image_data
        # Gemini supports inline_data with base64
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": base64_image
            }
        })

    request_body = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000,
        }
    }

    async def make_request():
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}',
                headers={'Content-Type': 'application/json'},
                json=request_body
            ) as response:
                return await response.json()

    result = await with_timeout(make_request(), timeout_seconds, 'GEMINI')

    # Extract text from Gemini response
    text = ''
    if isinstance(result.get('candidates'), list):
        for candidate in result['candidates']:
            if isinstance(candidate.get('content', {}).get('parts'), list):
                for part in candidate['content']['parts']:
                    text += part.get('text', '')

    metadata = {
        'model': 'gemini-1.5-flash',
        'tokens': result.get('usageMetadata', {}).get('totalTokenCount', 0)
    }

    return text, metadata


async def get_ai_response(
    message: str,
    message_length: int,
    image_data: Optional[Tuple[str, str]] = None
) -> tuple[str, dict]:
    """
    Get AI response with fallback chain: GPT-5 → Claude → Gemini
    Returns: (response_text, metadata)
    image_data: Optional tuple of (base64_image, mime_type)
    """
    # Select model based on message complexity and image presence
    has_image = image_data is not None

    if has_image:
        # For images, always use the most capable model with longer timeout
        selected_model = 'gpt-5'
        max_output = 8000  # More tokens for image analysis
        timeout = 300  # 5 minutes for image processing
        logger.info("[AI] Image detected - using GPT-5 with extended settings")
    elif message_length > 200:
        selected_model = 'gpt-5'
        max_output = 4000
        timeout = 180  # 3 minutes
    elif message_length > 50:
        selected_model = 'gpt-5-mini'
        max_output = 2000
        timeout = 120  # 2 minutes
    else:
        selected_model = 'gpt-5-nano'
        max_output = 1000
        timeout = 90  # 1.5 minutes

    logger.info(f"[AI] Selected model: {selected_model}, has_image: {has_image}")

    # Try OpenAI GPT-5 first
    if OPENAI_API_KEY:
        try:
            logger.info("[AI] Attempting OpenAI GPT-5...")
            response, metadata = await call_openai_responses_api(
                message, selected_model, max_output, timeout, image_data
            )
            if response and response.strip():
                logger.info(f"[AI] ✅ OpenAI success: {len(response)} chars")
                return response, metadata
        except Exception as e:
            logger.error(f"[AI] OpenAI failed: {e}")

    # Fallback to Claude
    if CLAUDE_API_KEY:
        try:
            logger.info("[AI] Attempting Claude fallback...")
            fallback_timeout = 180 if has_image else 120
            response, metadata = await call_claude_api(message, fallback_timeout, image_data)
            if response and response.strip():
                logger.info(f"[AI] ✅ Claude success: {len(response)} chars")
                return response, metadata
        except Exception as e:
            logger.error(f"[AI] Claude failed: {e}")

    # Fallback to Gemini
    if GEMINI_API_KEY:
        try:
            logger.info("[AI] Attempting Gemini fallback...")
            fallback_timeout = 180 if has_image else 120
            response, metadata = await call_gemini_api(message, fallback_timeout, image_data)
            if response and response.strip():
                logger.info(f"[AI] ✅ Gemini success: {len(response)} chars")
                return response, metadata
        except Exception as e:
            logger.error(f"[AI] Gemini failed: {e}")

    raise Exception("All AI services failed to respond")


# ============================================================================
# Owner Verification and Admin Functions
# ============================================================================

def is_owner(user_id: int) -> bool:
    """Check if user is the bot owner"""
    if not OWNER_USER_ID:
        return False
    try:
        return str(user_id) == str(OWNER_USER_ID)
    except:
        return False


def is_bot_mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if bot is mentioned in the message.
    Returns True if:
    - It's a private chat
    - Bot is mentioned via @username
    - Message is a reply to bot's message
    """
    chat_type = update.effective_chat.type

    # Always respond in private chats
    if chat_type == 'private':
        return True

    # In groups/supergroups, check if bot is mentioned
    message = update.message

    # Check if message is a reply to the bot
    if message.reply_to_message and message.reply_to_message.from_user.is_bot:
        bot_id = context.bot.id
        if message.reply_to_message.from_user.id == bot_id:
            return True

    # Check if bot is mentioned via @username in text
    if message.text:
        # Check for @username mention
        bot_username = context.bot.username
        if bot_username and f"@{bot_username}" in message.text:
            return True

        # Check for mentions in entities
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention_text = message.text[entity.offset:entity.offset + entity.length]
                    if mention_text == f"@{bot_username}":
                        return True

    # Check for photo with caption mentioning bot
    if message.caption:
        bot_username = context.bot.username
        if bot_username and f"@{bot_username}" in message.caption:
            return True

        # Check caption entities
        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type == "mention":
                    mention_text = message.caption[entity.offset:entity.offset + entity.length]
                    if mention_text == f"@{bot_username}":
                        return True

    return False


async def owner_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verify owner access and notify if unauthorized"""
    user_id = update.effective_user.id

    if is_owner(user_id):
        return True

    # Notify unauthorized access attempt
    await update.message.reply_text(
        "⛔ Unauthorized Access\n\n"
        "This command is only available to the bot owner.\n\n"
        "If you are the bot owner, please configure your OWNER_USER_ID in the .env file."
    )
    logger.warning(f"[ADMIN] Unauthorized access attempt by user {user_id} ({update.effective_user.username})")
    return False


# ============================================================================
# Advertisement Functions
# ============================================================================

async def send_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send advertisement after AI response if enabled"""
    if not ad_manager.is_enabled():
        logger.info("[AD] Advertisements disabled")
        return

    try:
        ad_type = ad_manager.get_type()

        if ad_type == 'image':
            file_id = ad_manager.get_image_file_id()
            caption = ad_manager.get_image_caption()

            if file_id:
                # Send image advertisement
                logger.info(f"[AD] Sending image advertisement to chat {update.effective_chat.id}")
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                logger.warning("[AD] Image ad enabled but no image file_id configured")

        elif ad_type == 'text':
            text = ad_manager.get_text()

            if text:
                # Send text advertisement
                logger.info(f"[AD] Sending text advertisement to chat {update.effective_chat.id}")
                await update.message.reply_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                logger.warning("[AD] Text ad enabled but no text configured")

    except Exception as e:
        logger.error(f"[AD] Failed to send advertisement: {e}")


async def post_scheduled_ad(context: ContextTypes.DEFAULT_TYPE, ad_id: str, ad_data: dict):
    """Post a scheduled advertisement to target groups"""
    try:
        ad_type = ad_data.get('type')
        target_groups = ad_data.get('target_groups', [])
        content = ad_data.get('content', {})

        # Delete old messages first
        old_messages = ad_scheduler.get_posted_messages(ad_id)
        for chat_id, message_id in old_messages.items():
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"[SCHEDULER] Deleted old ad message {message_id} from chat {chat_id}")
            except Exception as e:
                logger.warning(f"[SCHEDULER] Failed to delete old message: {e}")

        # Post new ad to all target groups
        for chat_id in target_groups:
            try:
                if ad_type == 'image':
                    file_id = content.get('file_id')
                    caption = content.get('caption', '')

                    if file_id:
                        message = await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=file_id,
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        ad_scheduler.mark_as_posted(ad_id, chat_id, message.message_id)
                        logger.info(f"[SCHEDULER] Posted image ad '{ad_data['name']}' to chat {chat_id}")

                elif ad_type == 'text':
                    text = content.get('text', '')

                    if text:
                        message = await context.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        ad_scheduler.mark_as_posted(ad_id, chat_id, message.message_id)
                        logger.info(f"[SCHEDULER] Posted text ad '{ad_data['name']}' to chat {chat_id}")

            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to post ad to chat {chat_id}: {e}")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error posting scheduled ad: {e}")


async def check_and_post_scheduled_ads(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check and post scheduled advertisements"""
    try:
        ads_to_post = ad_scheduler.get_ads_to_post()

        if ads_to_post:
            logger.info(f"[SCHEDULER] Found {len(ads_to_post)} ads to post")

            for ad_id, ad_data in ads_to_post:
                await post_scheduled_ad(context, ad_id, ad_data)

    except Exception as e:
        logger.error(f"[SCHEDULER] Error in background task: {e}")


async def start_scheduler_task(application):
    """Start the background scheduler task"""
    job_queue = application.job_queue

    if job_queue is None:
        logger.error("[SCHEDULER] JobQueue not available! Install with: pip install python-telegram-bot[job-queue]")
        return

    # Run every 5 minutes
    job_queue.run_repeating(
        check_and_post_scheduled_ads,
        interval=300,  # 5 minutes in seconds
        first=10  # Start after 10 seconds
    )

    logger.info("[SCHEDULER] Background task started (runs every 5 minutes)")


# ============================================================================
# Command Handlers
# ============================================================================

def get_main_keyboard(user_id: int = None) -> ReplyKeyboardMarkup:
    """Generate main reply keyboard with quick-access buttons (only for private chats)"""
    global OWNER_AI_ENABLED
    # Owner gets additional admin buttons
    if user_id and is_owner(user_id):
        # Show appropriate AI toggle button based on current state
        ai_button = "🔊 Enable AI" if not OWNER_AI_ENABLED else "🔇 Disable AI"
        keyboard = [
            [KeyboardButton("💳 Credits"), KeyboardButton("📊 Status")],
            [KeyboardButton("🛒 Buy Credits"), KeyboardButton("❓ Help")],
            [KeyboardButton("⚙️ Settings"), KeyboardButton("📢 Broadcast")],
            [KeyboardButton("📺 Set Ad"), KeyboardButton("🔄 Toggle Ad")],
            [KeyboardButton(ai_button), KeyboardButton("🔗 Links")]
        ]
    else:
        # Regular users get standard keyboard
        keyboard = [
            [KeyboardButton("💳 Credits"), KeyboardButton("📊 Status")],
            [KeyboardButton("🛒 Buy Credits"), KeyboardButton("❓ Help")],
            [KeyboardButton("🔗 Links")]
        ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False  # Don't hide after use
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    # Track this chat for broadcasting
    chat = update.effective_chat
    usage_tracker.track_chat(chat.id, chat.type, chat.title)

    # Log user ID for owner configuration
    user_id = update.effective_user.id
    logger.info(f"[BOT] /start from user {user_id} ({update.effective_user.username}) in chat {chat.id} ({chat.type})")

    welcome_message = (
        "🤖 Welcome to NovaAiBot!\n\n"
        "I'm here to answer your questions using advanced AI technology.\n\n"
        "📝 How to use:\n"
        "• Send me text questions directly\n"
        "• Send photos of problems, diagrams, or equations\n"
        "• Add a caption to photos for specific questions\n"
        "• You start with 10 FREE credits\n\n"
        "🎯 Perfect for:\n"
        "• Physics problems with diagrams\n"
        "• Chemistry equations and structures\n"
        "• Biology diagrams and illustrations\n"
        "• Math equations from textbooks\n\n"
        "💡 Want unlimited access?\n"
        f"Download Nova Learn App: {NOVA_LEARN_APP_LINK}\n\n"
        f"📢 Join our WhatsApp channel: {WHATSAPP_CHANNEL_LINK}\n\n"
        "Send me a question or photo to get started!"
    )

    # Send welcome message with keyboard (only in private chats)
    reply_markup = get_main_keyboard(update.effective_user.id) if chat.type == 'private' else None
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /keyboard command - Force show keyboard"""
    if update.effective_chat.type != 'private':
        await update.message.reply_text("⚠️ Keyboard buttons are only available in private chats.")
        return

    await update.message.reply_text(
        "✅ Keyboard activated!\n\n"
        "You can now use the quick-access buttons below 👇",
        reply_markup=get_main_keyboard(update.effective_user.id)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_message = (
        "🆘 NovaAiBot Help\n\n"
        "**Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/status - Check your credit balance\n"
        "/credits - View available credit packages\n"
        "/buy - Purchase credits with Telegram Stars ⭐\n"
        "/keyboard - Show quick-access buttons\n\n"
        "**How to Ask Questions:**\n\n"
        "📝 Text Questions:\n"
        "Just type and send your question\n\n"
        "📸 Image Questions:\n"
        "1. Take a photo of your problem/diagram\n"
        "2. Add a caption (optional but recommended)\n"
        "3. Send it to the bot\n\n"
        "**Examples:**\n"
        "• Photo of physics problem + caption: \"Solve this\"\n"
        "• Photo of chemical structure + caption: \"What compound is this?\"\n"
        "• Photo of biology diagram + caption: \"Explain this process\"\n"
        "• Photo without caption: Bot will analyze and explain\n\n"
        "**Credit System:**\n"
        f"• Text question: {usage_tracker.TEXT_QUESTION_COST} credit\n"
        f"• Image question: {usage_tracker.IMAGE_QUESTION_COST} credits\n"
        f"• New users start with {usage_tracker.INITIAL_CREDITS} free credits\n"
        f"• Daily limit: {usage_tracker.DAILY_CREDIT_LIMIT} credits per day\n"
        "• Images must be under 5MB and clear\n"
        "• Buy more credits with /buy using Telegram Stars ⭐\n\n"
        f"📱 For unlimited access, download: {NOVA_LEARN_APP_LINK}\n"
        f"📢 Join our WhatsApp: {WHATSAPP_CHANNEL_LINK}"
    )

    # Show keyboard in private chats
    reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - Show credit balance"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # Ensure user exists and get credits
    usage_tracker._ensure_user_exists(user_id, username)
    credits = usage_tracker.get_credits(user_id)
    daily_usage = usage_tracker.get_daily_usage(user_id)
    daily_limit = usage_tracker.DAILY_CREDIT_LIMIT

    # Calculate what they can do
    text_questions = credits // usage_tracker.TEXT_QUESTION_COST
    image_questions = credits // usage_tracker.IMAGE_QUESTION_COST
    remaining_daily = max(0, daily_limit - daily_usage)

    status_message = (
        f"💳 **Your NovaAI Credits**\n\n"
        f"💰 Current Balance: **{credits} credits**\n"
        f"📊 Daily Usage: **{daily_usage}/{daily_limit} credits**\n"
        f"⏰ Daily Remaining: **{remaining_daily} credits**\n\n"
        f"📝 You can ask:\n"
        f"• {text_questions} text questions (1 credit each)\n"
        f"• {image_questions} image questions (2 credits each)\n\n"
    )

    if credits > 0:
        status_message += "✨ Send me your question to get started!"
    else:
        status_message += (
            "⚠️ You're out of credits!\n\n"
            "Use /credits to see available packages\n\n"
            f"📱 Or download Nova Learn App:\n{NOVA_LEARN_APP_LINK}"
        )

    # Show keyboard in private chats
    reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
    await update.message.reply_text(status_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /credits command - Show available credit packages"""
    user_id = update.effective_user.id
    current_credits = usage_tracker.get_credits(user_id)

    credits_message = (
        "💳 **NovaAI Credit Packages**\n\n"
        f"💰 Your Balance: **{current_credits} credits**\n\n"
        "📦 **Available Packages:**\n\n"
    )

    for package_id, package_info in usage_tracker.CREDIT_PACKAGES.items():
        credits_message += f"⭐ **{package_info['name']}**: {package_info['credits']} credits - {package_info['stars']} Stars\n"

    credits_message += (
        "\n\n💡 **Credit Costs:**\n"
        f"• Text question: {usage_tracker.TEXT_QUESTION_COST} credit\n"
        f"• Image question: {usage_tracker.IMAGE_QUESTION_COST} credits\n\n"
        "🌟 **Purchase with Telegram Stars:**\n"
        "Use /buy to purchase credits with Telegram Stars\n\n"
        "📱 **Or get unlimited access:**\n"
        f"Download Nova Learn App:\n{NOVA_LEARN_APP_LINK}\n\n"
        f"📢 Join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}"
    )

    # Show keyboard in private chats
    reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
    await update.message.reply_text(credits_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command - Show credit packages (Manual mode until Telegram Stars is available)"""
    # Only works in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ Credit purchases are only available in private chat.\n\n"
            "Please start a private chat with me using /start"
        )
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    current_credits = usage_tracker.get_credits(user_id)

    # TEMPORARY: Manual payment system until Telegram Stars is available in your region
    # To enable automatic Telegram Stars: Go to @BotFather → /mybots → Your Bot → Bot Settings → Payments → Telegram Stars

    buy_message = (
        "🛒 **Purchase NovaAI Credits**\n\n"
        f"💰 Your Current Balance: **{current_credits} credits**\n\n"
        "📦 **Available Packages:**\n\n"
    )

    for package_id, package_info in usage_tracker.CREDIT_PACKAGES.items():
        buy_message += (
            f"⭐ **{package_info['name']}** - {package_info['stars']} Stars\n"
            f"   • {package_info['credits']} credits - {package_info['description']}\n\n"
        )

    buy_message += (
        "\n💳 **How to Purchase:**\n\n"
        "⚠️ **Telegram Stars automatic payment is not yet available.**\n\n"
        "📝 **Manual Purchase Process:**\n"
        f"1️⃣ Your User ID: `{user_id}`\n"
        f"2️⃣ Your Username: @{username}\n"
        f"3️⃣ Contact the bot owner with:\n"
        f"   • Your User ID: {user_id}\n"
        "   • The package you want\n"
        "   • Payment method details\n\n"
        "4️⃣ After payment confirmation, credits will be added to your account using `/addcredits`\n\n"
        f"📱 **Alternative:** Download Nova Learn App for unlimited access:\n{NOVA_LEARN_APP_LINK}\n\n"
        "💡 **Note:** Automatic Telegram Stars payments will be enabled soon!"
    )

    # Show keyboard in private chats
    reply_markup = get_main_keyboard(update.effective_user.id)
    await update.message.reply_text(buy_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def handle_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy button callbacks and show_buy_menu"""
    query = update.callback_query
    await query.answer()

    # Handle show_buy_menu callback
    if query.data == "show_buy_menu":
        user_id = update.effective_user.id
        current_credits = usage_tracker.get_credits(user_id)

        # Create inline keyboard with package options
        keyboard = []
        for package_id, package_info in usage_tracker.CREDIT_PACKAGES.items():
            button_text = f"⭐ {package_info['name']} - {package_info['stars']} Stars"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"buy_{package_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        buy_message = (
            "🛒 **Purchase NovaAI Credits**\n\n"
            f"💰 Your Current Balance: **{current_credits} credits**\n\n"
            "📦 **Select a package to purchase:**\n\n"
            "Payment is securely processed through Telegram Stars.\n"
            "Credits will be added to your account immediately after payment."
        )

        await query.edit_message_text(buy_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return

    # Handle buy_<package_id> callbacks
    if query.data.startswith("buy_"):
        package_id = query.data.replace("buy_", "")

        if package_id not in usage_tracker.CREDIT_PACKAGES:
            await query.edit_message_text("❌ Invalid package selected.")
            return

        package = usage_tracker.CREDIT_PACKAGES[package_id]

        # Send invoice using Telegram Stars
        try:
            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title=package['name'],
                description=package['description'],
                payload=f"credits_{package_id}_{query.from_user.id}",  # Custom payload to identify the purchase
                currency="XTR",  # Telegram Stars currency code
                prices=[LabeledPrice(label=package['name'], amount=package['stars'])],
            )

            await query.edit_message_text(
                f"✅ **Invoice Sent!**\n\n"
                f"📦 Package: {package['name']}\n"
                f"💎 Credits: {package['credits']}\n"
                f"⭐ Price: {package['stars']} Telegram Stars\n\n"
                "Please complete the payment to receive your credits.",
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"[PAYMENT] Error sending invoice: {e}")
            await query.edit_message_text(
                "❌ Failed to create payment invoice.\n\n"
                "This could be because:\n"
                "• Bot payments are not enabled\n"
                "• There's a temporary issue\n\n"
                "Please try again later or contact support."
            )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout queries - validate before payment"""
    query = update.pre_checkout_query

    # Validate the payload
    payload = query.invoice_payload

    if not payload.startswith("credits_"):
        logger.error(f"[PAYMENT] Invalid payload: {payload}")
        await query.answer(ok=False, error_message="Invalid purchase. Please try again.")
        return

    # Parse payload: credits_<package_id>_<user_id>
    try:
        parts = payload.split("_")
        package_id = parts[1]
        user_id = int(parts[2])

        # Verify package exists
        if package_id not in usage_tracker.CREDIT_PACKAGES:
            logger.error(f"[PAYMENT] Invalid package: {package_id}")
            await query.answer(ok=False, error_message="Invalid package. Please try again.")
            return

        # Verify user
        if user_id != query.from_user.id:
            logger.error(f"[PAYMENT] User mismatch: {user_id} != {query.from_user.id}")
            await query.answer(ok=False, error_message="Invalid user. Please try again.")
            return

        # All checks passed
        logger.info(f"[PAYMENT] Pre-checkout OK for user {user_id}, package {package_id}")
        await query.answer(ok=True)

    except Exception as e:
        logger.error(f"[PAYMENT] Pre-checkout error: {e}")
        await query.answer(ok=False, error_message="Validation error. Please try again.")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payments - add credits to user"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    payment = update.message.successful_payment

    # Parse payload
    payload = payment.invoice_payload

    try:
        parts = payload.split("_")
        package_id = parts[1]

        if package_id not in usage_tracker.CREDIT_PACKAGES:
            logger.error(f"[PAYMENT] Invalid package in successful payment: {package_id}")
            await update.message.reply_text("❌ Error processing your payment. Please contact support.")
            return

        package = usage_tracker.CREDIT_PACKAGES[package_id]
        credits_to_add = package['credits']

        # Add credits to user
        new_balance = usage_tracker.add_credits(user_id, credits_to_add, username)

        logger.info(
            f"[PAYMENT] ✅ Payment successful! User {user_id} purchased {package_id} "
            f"for {package['stars']} stars. Added {credits_to_add} credits. New balance: {new_balance}"
        )

        # Send success message
        success_message = (
            "✅ **Payment Successful!**\n\n"
            f"🎁 Package: {package['name']}\n"
            f"💎 Credits Added: **{credits_to_add}**\n"
            f"💰 New Balance: **{new_balance} credits**\n\n"
            "Thank you for your purchase! 🎉\n\n"
            "You can now use your credits to ask questions.\n"
            "Just send me your question to get started!"
        )

        await update.message.reply_text(success_message, parse_mode=ParseMode.MARKDOWN)

        # Notify owner about the purchase (if owner is set)
        if OWNER_USER_ID:
            try:
                owner_notification = (
                    f"💰 **New Purchase!**\n\n"
                    f"👤 User: {username} (ID: {user_id})\n"
                    f"📦 Package: {package['name']}\n"
                    f"⭐ Stars: {package['stars']}\n"
                    f"💎 Credits: {credits_to_add}\n"
                    f"💰 User Balance: {new_balance}"
                )
                await context.bot.send_message(
                    chat_id=int(OWNER_USER_ID),
                    text=owner_notification,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"[PAYMENT] Failed to notify owner: {e}")

    except Exception as e:
        logger.error(f"[PAYMENT] Error processing successful payment: {e}")
        await update.message.reply_text(
            "⚠️ Payment received but there was an error adding credits.\n"
            "Please contact support with your payment details."
        )


async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle keyboard button presses"""
    text = update.message.text

    # Route to appropriate command based on button text
    if text == "💳 Credits":
        await credits_command(update, context)
    elif text == "📊 Status":
        await status_command(update, context)
    elif text == "🛒 Buy Credits":
        await buy_command(update, context)
    elif text == "❓ Help":
        await help_command(update, context)
    elif text == "🔗 Links":
        # Show useful links
        links_message = (
            "🔗 **NovaAI Links**\n\n"
            "📱 **Nova Learn App** (Unlimited Access):\n"
            f"{NOVA_LEARN_APP_LINK}\n\n"
            "📢 **WhatsApp Channel** (Updates & Support):\n"
            f"{WHATSAPP_CHANNEL_LINK}\n\n"
            "💡 **Join our community** for:\n"
            "• Latest updates and features\n"
            "• Study tips and resources\n"
            "• Special offers and promotions\n"
            "• 24/7 community support"
        )
        reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
        await update.message.reply_text(links_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    # Owner-only buttons
    elif text == "⚙️ Settings":
        await settings_command(update, context)
    elif text == "📢 Broadcast":
        await broadcast_command(update, context)
    elif text == "📺 Set Ad":
        await setad_command(update, context)
    elif text == "🔄 Toggle Ad":
        await togglead_command(update, context)
    elif text in ["🔇 Disable AI", "🔊 Enable AI"]:
        # Toggle AI response mode for owner
        global OWNER_AI_ENABLED
        OWNER_AI_ENABLED = not OWNER_AI_ENABLED
        status = "enabled" if OWNER_AI_ENABLED else "disabled"
        icon = "🔊" if OWNER_AI_ENABLED else "🔇"
        message = (
            f"{icon} **AI Mode {status.upper()}**\n\n"
            f"AI responses are now **{status}** for you.\n\n"
        )
        if OWNER_AI_ENABLED:
            message += "✅ Your messages will be processed as AI questions."
        else:
            message += (
                "⚠️ Your messages will NOT trigger AI responses.\n"
                "This is useful when you're doing admin work like:\n"
                "• Setting advertisements\n"
                "• Broadcasting messages\n"
                "• Managing bot settings\n\n"
                "Regular users are not affected by this setting."
            )
        reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        # Not a keyboard button, return None to allow next handler
        return None


async def addcredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addcredits command (Owner only) - Add credits to a user"""
    if not await owner_only(update, context):
        return

    # Only allow in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Owner commands only work in private chat with the bot.\n"
            "Please use these commands in a direct message, not in groups.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse command: /addcredits <user_id> <amount>
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "Usage: `/addcredits <user_id> <amount>`\n\n"
            "Example:\n"
            "`/addcredits 123456789 50`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])

        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive!")
            return

        new_balance = usage_tracker.add_credits(target_user_id, amount)

        await update.message.reply_text(
            f"✅ **Credits Added!**\n\n"
            f"User ID: `{target_user_id}`\n"
            f"Added: **{amount} credits**\n"
            f"New Balance: **{new_balance} credits**",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"[ADMIN] Owner added {amount} credits to user {target_user_id}")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount. Must be numbers.")
    except Exception as e:
        logger.error(f"[ADMIN] Error adding credits: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def setcredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setcredits command (Owner only) - Set user credits to specific amount"""
    if not await owner_only(update, context):
        return

    # Only allow in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Owner commands only work in private chat with the bot.\n"
            "Please use these commands in a direct message, not in groups.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse command: /setcredits <user_id> <amount>
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "Usage: `/setcredits <user_id> <amount>`\n\n"
            "Example:\n"
            "`/setcredits 123456789 100`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])

        if amount < 0:
            await update.message.reply_text("❌ Amount cannot be negative!")
            return

        new_balance = usage_tracker.set_credits(target_user_id, amount)

        await update.message.reply_text(
            f"✅ **Credits Set!**\n\n"
            f"User ID: `{target_user_id}`\n"
            f"New Balance: **{new_balance} credits**",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"[ADMIN] Owner set user {target_user_id} credits to {amount}")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount. Must be numbers.")
    except Exception as e:
        logger.error(f"[ADMIN] Error setting credits: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command (Owner only)"""
    if not await owner_only(update, context):
        return

    # Only allow in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Owner commands only work in private chat with the bot.\n"
            "Please use these commands in a direct message, not in groups.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Get statistics
    stats = usage_tracker.get_statistics()

    # Create inline keyboard with settings options
    keyboard = [
        [InlineKeyboardButton("📊 View Statistics", callback_data="settings_stats")],
        [InlineKeyboardButton("📢 Broadcast to Users", callback_data="settings_broadcast_users")],
        [InlineKeyboardButton("📢 Broadcast to Groups", callback_data="settings_broadcast_groups")],
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="settings_broadcast_all")],
        [InlineKeyboardButton("❌ Close", callback_data="settings_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_message = (
        "⚙️ **Bot Settings** (Owner Only)\n\n"
        f"👥 Total Users: {stats['total_users']}\n"
        f"❓ Total Questions: {stats['total_questions']}\n"
        f"💬 User Chats: {stats['user_chats']}\n"
        f"👥 Group Chats: {stats['group_chats']}\n\n"
        "Choose an option below:"
    )

    await update.message.reply_text(settings_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not is_owner(user_id):
        await query.edit_message_text("⛔ Unauthorized access. This feature is only for the bot owner.")
        return

    data = query.data

    if data == "settings_stats":
        # Show detailed statistics
        stats = usage_tracker.get_statistics()
        stats_message = (
            "📊 **Detailed Statistics**\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"❓ Total Questions Asked: {stats['total_questions']}\n"
            f"💬 Active User Chats: {stats['user_chats']}\n"
            f"👥 Active Group Chats: {stats['group_chats']}\n"
            f"📱 Total Chats: {stats['total_chats']}\n\n"
            "Use /settings to return to main menu."
        )
        await query.edit_message_text(stats_message, parse_mode=ParseMode.MARKDOWN)

    elif data == "settings_broadcast_users":
        await query.edit_message_text(
            "📢 **Broadcast to Users**\n\n"
            "**Text Broadcast:**\n"
            "`/broadcast users <your message>`\n\n"
            "**Image Broadcast:**\n"
            "Send photo with caption: `#broadcast users <message>`\n\n"
            "Example:\n"
            "`/broadcast users Hello! Check out our new feature!`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "settings_broadcast_groups":
        await query.edit_message_text(
            "📢 **Broadcast to Groups**\n\n"
            "**Text Broadcast:**\n"
            "`/broadcast groups <your message>`\n\n"
            "**Image Broadcast:**\n"
            "Send photo with caption: `#broadcast groups <message>`\n\n"
            "Example:\n"
            "`/broadcast groups Important update for all groups!`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "settings_broadcast_all":
        await query.edit_message_text(
            "📢 **Broadcast to All**\n\n"
            "**Text Broadcast:**\n"
            "`/broadcast all <your message>`\n\n"
            "**Image Broadcast:**\n"
            "Send photo with caption: `#broadcast all <message>`\n\n"
            "Examples:\n"
            "• Text: `/broadcast all New feature available now!`\n"
            "• Image: Send photo with caption `#broadcast all Check this out!`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "settings_close":
        await query.edit_message_text("⚙️ Settings closed.")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command (Owner only) - Send messages to all users/groups"""
    if not await owner_only(update, context):
        return

    # Only allow in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Owner commands only work in private chat with the bot.\n"
            "Please use these commands in a direct message, not in groups.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse command: /broadcast <target> <message>
    # target can be: users, groups, or all
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "Usage:\n"
            "`/broadcast users <message>` - Send to all users\n"
            "`/broadcast groups <message>` - Send to all groups\n"
            "`/broadcast all <message>` - Send to everyone\n\n"
            "Example:\n"
            "`/broadcast all Check out our new features!`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    target = context.args[0].lower()
    message = ' '.join(context.args[1:])

    if target not in ['users', 'groups', 'all']:
        await update.message.reply_text(
            "❌ Invalid target. Use: `users`, `groups`, or `all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Get chat IDs based on target
    if target == 'users':
        chat_ids = usage_tracker.get_all_user_chats()
        target_name = "users"
    elif target == 'groups':
        chat_ids = usage_tracker.get_all_group_chats()
        target_name = "groups"
    else:  # all
        chat_ids = usage_tracker.get_all_user_chats() + usage_tracker.get_all_group_chats()
        target_name = "all users and groups"

    if not chat_ids:
        await update.message.reply_text(f"⚠️ No {target_name} found to broadcast to.")
        return

    # Confirm broadcast
    await update.message.reply_text(
        f"📢 **Broadcasting to {len(chat_ids)} {target_name}...**\n\n"
        f"Message: {message}\n\n"
        "Please wait..."
    )

    # Send broadcast
    success_count = 0
    fail_count = 0

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📢 **Announcement from NovaAI**\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Small delay to avoid rate limiting
        except Exception as e:
            logger.error(f"[BROADCAST] Failed to send to {chat_id}: {e}")
            fail_count += 1

    # Report results
    result_message = (
        f"✅ **Broadcast Complete**\n\n"
        f"📊 Results:\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📱 Total: {len(chat_ids)}"
    )
    await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"[BROADCAST] Completed: {success_count} sent, {fail_count} failed to {target_name}")


# ============================================================================
# Two-Step Image Broadcast System
# ============================================================================

async def start_image_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start image broadcast - Owner sends image first"""
    user_id = update.effective_user.id

    if not is_owner(user_id):
        await update.message.reply_text("⛔ This command is only for the bot owner.")
        return ConversationHandler.END

    # Check if this is a photo message
    if update.message.photo:
        # Store the photo
        photo = update.message.photo[-1]
        context.user_data['broadcast_photo'] = photo.file_id
        logger.info(f"[BROADCAST_IMG] Owner sent image, file_id: {photo.file_id}")

        # Ask for target and message
        keyboard = [
            [InlineKeyboardButton("📢 All", callback_data="bcast_all")],
            [InlineKeyboardButton("👥 Users Only", callback_data="bcast_users")],
            [InlineKeyboardButton("👥 Groups Only", callback_data="bcast_groups")],
            [InlineKeyboardButton("❌ Cancel", callback_data="bcast_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📸 **Image received!**\n\n"
            "Who should receive this broadcast?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_BROADCAST_CAPTION
    else:
        await update.message.reply_text(
            "📸 **Start Image Broadcast**\n\n"
            "Send me an image to broadcast.\n\n"
            "Use /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_BROADCAST_CAPTION


async def handle_broadcast_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target selection for broadcast"""
    query = update.callback_query
    await query.answer()

    if query.data == "bcast_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        return ConversationHandler.END

    # Store target
    target_map = {
        "bcast_all": "all",
        "bcast_users": "users",
        "bcast_groups": "groups"
    }
    context.user_data['broadcast_target'] = target_map[query.data]

    await query.edit_message_text(
        "✍️ **Now send your message**\n\n"
        "This will be the caption for your image.\n\n"
        "Use /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_BROADCAST_CAPTION


async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the message/caption and send broadcast"""
    user_id = update.effective_user.id

    if not is_owner(user_id):
        return ConversationHandler.END

    # Get stored data
    photo_file_id = context.user_data.get('broadcast_photo')
    target = context.user_data.get('broadcast_target')
    message = update.message.text

    if not photo_file_id or not target:
        await update.message.reply_text("❌ Error: Missing broadcast data. Please start over with /broadcastimg")
        return ConversationHandler.END

    # Get chat IDs based on target
    if target == 'users':
        chat_ids = usage_tracker.get_all_user_chats()
        target_name = "users"
    elif target == 'groups':
        chat_ids = usage_tracker.get_all_group_chats()
        target_name = "groups"
    else:  # all
        chat_ids = usage_tracker.get_all_user_chats() + usage_tracker.get_all_group_chats()
        target_name = "all users and groups"

    if not chat_ids:
        await update.message.reply_text(f"⚠️ No {target_name} found to broadcast to.")
        return ConversationHandler.END

    # Confirm and start broadcast
    await update.message.reply_text(
        f"📢 **Broadcasting to {len(chat_ids)} {target_name}...**\n\n"
        f"Message: {message}\n\n"
        "Please wait...",
        parse_mode=ParseMode.MARKDOWN
    )

    # Send broadcast
    success_count = 0
    fail_count = 0
    full_caption = f"📢 **Announcement from NovaAI**\n\n{message}" if message else "📢 **Announcement from NovaAI**"

    for chat_id in chat_ids:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_file_id,
                caption=full_caption,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"[BROADCAST_IMG] Failed to send to {chat_id}: {e}")
            fail_count += 1

    # Report results
    result_message = (
        f"✅ **Broadcast Complete!**\n\n"
        f"📊 Results:\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📱 Total: {len(chat_ids)}"
    )
    await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"[BROADCAST_IMG] Completed: {success_count} sent, {fail_count} failed to {target_name}")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the broadcast conversation"""
    context.user_data.clear()
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END


async def broadcast_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """OLD Handler - kept for backward compatibility with #broadcast captions"""
    user_id = update.effective_user.id

    logger.info(f"[BROADCAST_IMG] Handler triggered by user {user_id}")

    # Only owner can broadcast
    if not is_owner(user_id):
        logger.warning(f"[BROADCAST_IMG] Non-owner user {user_id} tried to broadcast")
        return  # Silently ignore non-owner photo messages with #broadcast

    caption = update.message.caption or ""
    logger.info(f"[BROADCAST_IMG] Caption: '{caption}'")
    logger.info(f"[BROADCAST_IMG] Caption length: {len(caption)}, First 20 chars: {repr(caption[:20])}")

    # Check if caption starts with #broadcast (case-sensitive)
    if not caption.lower().startswith("#broadcast "):
        logger.info(f"[BROADCAST_IMG] Caption doesn't start with '#broadcast ', skipping")
        return  # Not a broadcast image

    # Parse the caption: #broadcast <target> <message>
    parts = caption.split(None, 2)  # Split into max 3 parts
    logger.info(f"[BROADCAST_IMG] Parsed parts: {parts}")

    if len(parts) < 2:
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "To broadcast an image, send a photo with caption:\n"
            "`#broadcast users <message>`\n"
            "`#broadcast groups <message>`\n"
            "`#broadcast all <message>`\n\n"
            "Example:\n"
            "Send photo with caption: `#broadcast all Check out this new feature!`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    target = parts[1].lower()
    message = parts[2] if len(parts) > 2 else ""

    if target not in ['users', 'groups', 'all']:
        await update.message.reply_text(
            "❌ Invalid target. Use: `users`, `groups`, or `all`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Get chat IDs based on target
    if target == 'users':
        chat_ids = usage_tracker.get_all_user_chats()
        target_name = "users"
    elif target == 'groups':
        chat_ids = usage_tracker.get_all_group_chats()
        target_name = "groups"
    else:  # all
        chat_ids = usage_tracker.get_all_user_chats() + usage_tracker.get_all_group_chats()
        target_name = "all users and groups"

    if not chat_ids:
        await update.message.reply_text(f"⚠️ No {target_name} found to broadcast to.")
        return

    # Get the photo
    photo = update.message.photo[-1]  # Get largest photo

    # Confirm broadcast
    await update.message.reply_text(
        f"📢 **Broadcasting image to {len(chat_ids)} {target_name}...**\n\n"
        f"Caption: {message if message else '(no caption)'}\n\n"
        "Please wait..."
    )

    # Send broadcast
    success_count = 0
    fail_count = 0

    # Prepare caption with announcement header
    full_caption = f"📢 **Announcement from NovaAI**\n\n{message}" if message else "📢 **Announcement from NovaAI**"

    for chat_id in chat_ids:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo.file_id,
                caption=full_caption,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Small delay to avoid rate limiting
        except Exception as e:
            logger.error(f"[BROADCAST_IMG] Failed to send to {chat_id}: {e}")
            fail_count += 1

    # Report results
    result_message = (
        f"✅ **Image Broadcast Complete**\n\n"
        f"📊 Results:\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📱 Total: {len(chat_ids)}"
    )
    await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"[BROADCAST_IMG] Completed: {success_count} sent, {fail_count} failed to {target_name}")


# ============================================================================
# Advertisement Configuration Handlers (Owner Only)
# ============================================================================

async def setad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start ad configuration process (Owner only)"""
    if not await owner_only(update, context):
        return ConversationHandler.END

    # Only allow in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Owner commands only work in private chat with the bot.\n"
            "Please use these commands in a direct message, not in groups.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # Show options for ad type
    keyboard = [
        [InlineKeyboardButton("📝 Set Text Ad", callback_data="adtype_text")],
        [InlineKeyboardButton("🖼️ Set Image Ad", callback_data="adtype_image")],
        [InlineKeyboardButton("❌ Cancel", callback_data="adtype_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    current_status = "✅ Enabled" if ad_manager.is_enabled() else "❌ Disabled"
    current_type = ad_manager.get_type()

    await update.message.reply_text(
        f"📢 **Advertisement Configuration**\n\n"
        f"**Current Status:** {current_status}\n"
        f"**Current Type:** {current_type.capitalize()}\n\n"
        "**What would you like to set?**",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_AD_IMAGE


async def handle_ad_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad type selection"""
    query = update.callback_query
    await query.answer()

    if query.data == "adtype_cancel":
        await query.edit_message_text("❌ Ad configuration cancelled.")
        return ConversationHandler.END

    if query.data == "adtype_text":
        # Text ad configuration
        await query.edit_message_text(
            "📝 **Set Text Advertisement**\n\n"
            "Please send the text you want to display as an advertisement.\n\n"
            "You can use Markdown formatting:\n"
            "• **Bold text**\n"
            "• *Italic text*\n"
            "• [Links](https://example.com)\n\n"
            "Send /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['ad_type'] = 'text'
        return WAITING_FOR_AD_CAPTION

    elif query.data == "adtype_image":
        # Image ad configuration
        await query.edit_message_text(
            "🖼️ **Set Image Advertisement**\n\n"
            "📸 **Step 1:** Please send the image for your advertisement.\n\n"
            "The image should be:\n"
            "• Clear and high quality\n"
            "• Under 5MB in size\n"
            "• Relevant to your advertisement\n\n"
            "Send /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['ad_type'] = 'image'
        return WAITING_FOR_AD_IMAGE


async def handle_ad_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad image upload"""
    user_id = update.effective_user.id

    if not is_owner(user_id):
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text(
            "⚠️ Please send an image, not text.\n\n"
            "Send /cancel to cancel."
        )
        return WAITING_FOR_AD_IMAGE

    # Get the photo
    photo = update.message.photo[-1]  # Get largest size
    context.user_data['ad_image_file_id'] = photo.file_id

    logger.info(f"[AD_CONFIG] Owner uploaded ad image, file_id: {photo.file_id}")

    await update.message.reply_text(
        "✅ **Image Received!**\n\n"
        "📝 **Step 2:** Now send the caption for this advertisement.\n\n"
        "You can use Markdown formatting:\n"
        "• **Bold text**\n"
        "• *Italic text*\n"
        "• [Links](https://example.com)\n\n"
        "Send /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_AD_CAPTION


async def handle_ad_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad caption/text"""
    user_id = update.effective_user.id

    if not is_owner(user_id):
        return ConversationHandler.END

    ad_type = context.user_data.get('ad_type', 'text')
    caption_or_text = update.message.text

    if ad_type == 'image':
        # Image ad
        file_id = context.user_data.get('ad_image_file_id')

        if not file_id:
            await update.message.reply_text("❌ Error: Image file_id not found. Please start over with /setad")
            return ConversationHandler.END

        # Save image ad
        ad_manager.set_image_ad(file_id, caption_or_text)

        # Send preview
        await update.message.reply_text("📸 **Preview of your advertisement:**")
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=file_id,
            caption=caption_or_text,
            parse_mode=ParseMode.MARKDOWN
        )

        await update.message.reply_text(
            "✅ **Image Advertisement Set Successfully!**\n\n"
            "Your image ad is now configured.\n\n"
            "Use `/togglead` to enable/disable advertisements.\n"
            f"Current status: {'✅ Enabled' if ad_manager.is_enabled() else '❌ Disabled'}",
            parse_mode=ParseMode.MARKDOWN
        )

    else:
        # Text ad
        ad_manager.set_text_ad(caption_or_text)

        # Send preview
        await update.message.reply_text(
            f"📝 **Preview of your advertisement:**\n\n{caption_or_text}",
            parse_mode=ParseMode.MARKDOWN
        )

        await update.message.reply_text(
            "✅ **Text Advertisement Set Successfully!**\n\n"
            "Your text ad is now configured.\n\n"
            "Use `/togglead` to enable/disable advertisements.\n"
            f"Current status: {'✅ Enabled' if ad_manager.is_enabled() else '❌ Disabled'}",
            parse_mode=ParseMode.MARKDOWN
        )

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_ad_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ad configuration"""
    context.user_data.clear()
    await update.message.reply_text("❌ Advertisement configuration cancelled.")
    return ConversationHandler.END


async def togglead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle advertisement on/off (Owner only)"""
    if not await owner_only(update, context):
        return

    # Only allow in private chats
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Owner commands only work in private chat with the bot.\n"
            "Please use these commands in a direct message, not in groups.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    new_status = ad_manager.toggle()
    status_text = "✅ Enabled" if new_status else "❌ Disabled"
    emoji = "🟢" if new_status else "🔴"

    current_type = ad_manager.get_type()

    message = (
        f"{emoji} **Advertisements {status_text}**\n\n"
        f"**Type:** {current_type.capitalize()}\n\n"
    )

    if new_status:
        if current_type == 'image':
            file_id = ad_manager.get_image_file_id()
            if not file_id:
                message += "⚠️ **Warning:** No image ad configured yet!\nUse /setad to configure."
        else:
            text = ad_manager.get_text()
            if not text:
                message += "⚠️ **Warning:** No text ad configured yet!\nUse /setad to configure."

    message += f"\n💡 Use /setad to change the advertisement."

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


# ============================================================================
# Scheduled Advertisement Management Handlers (Owner Only)
# ============================================================================

async def createad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a new scheduled advertisement (Owner only)"""
    if not await owner_only(update, context):
        return ConversationHandler.END

    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "⚠️ **Admin Commands in Private Only**\n\n"
            "Please use this command in a direct message with the bot.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📢 **Create New Scheduled Advertisement**\n\n"
        "Let's create a new advertisement that will be automatically posted to your groups.\n\n"
        "**Step 1:** Please enter a name for this advertisement.\n"
        "Example: 'Weekly Promo', 'Study Tips', etc.\n\n"
        "Send /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_AD_NAME


async def handle_ad_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle advertisement name input"""
    name = update.message.text.strip()

    if len(name) < 3:
        await update.message.reply_text(
            "⚠️ Name must be at least 3 characters long.\n\n"
            "Please try again or send /cancel to cancel."
        )
        return WAITING_FOR_AD_NAME

    context.user_data['scheduled_ad_name'] = name

    keyboard = [
        [InlineKeyboardButton("📝 Text Ad", callback_data="schedtype_text")],
        [InlineKeyboardButton("🖼️ Image Ad", callback_data="schedtype_image")],
        [InlineKeyboardButton("❌ Cancel", callback_data="schedtype_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Ad Name: **{name}**\n\n"
        "**Step 2:** Choose the type of advertisement:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_FOR_AD_TYPE_SELECT


async def handle_scheduled_ad_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad type selection for scheduled ads"""
    query = update.callback_query
    await query.answer()

    if query.data == "schedtype_cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Advertisement creation cancelled.")
        return ConversationHandler.END

    ad_type = query.data.replace("schedtype_", "")
    context.user_data['scheduled_ad_type'] = ad_type

    if ad_type == 'text':
        await query.edit_message_text(
            "📝 **Step 3:** Send the text content for your advertisement.\n\n"
            "You can use Markdown formatting:\n"
            "• **Bold text**\n"
            "• *Italic text*\n"
            "• [Links](https://example.com)\n\n"
            "Send /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:  # image
        await query.edit_message_text(
            "🖼️ **Step 3:** Send the image for your advertisement.\n\n"
            "Requirements:\n"
            "• Clear and high quality\n"
            "• Under 5MB in size\n\n"
            "You can add a caption after sending the image.\n\n"
            "Send /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )

    return WAITING_FOR_AD_CONTENT


async def handle_scheduled_ad_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad content (text or image)"""
    ad_type = context.user_data.get('scheduled_ad_type')

    if ad_type == 'text':
        if not update.message.text:
            await update.message.reply_text(
                "⚠️ Please send text content.\n\n"
                "Send /cancel to cancel."
            )
            return WAITING_FOR_AD_CONTENT

        context.user_data['scheduled_ad_content'] = {
            'text': update.message.text
        }

        await update.message.reply_text(
            f"✅ **Content saved!**\n\n"
            f"Preview:\n{update.message.text}\n\n"
            "**Step 4:** Set the posting interval in hours.\n"
            "How often should this ad be posted?\n\n"
            "Examples:\n"
            "• 1 = Every hour\n"
            "• 6 = Every 6 hours\n"
            "• 24 = Once per day\n"
            "• 168 = Once per week\n\n"
            "Enter a number (minimum 1):",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_AD_SCHEDULE_INTERVAL

    elif ad_type == 'image':
        if not update.message.photo:
            await update.message.reply_text(
                "⚠️ Please send an image.\n\n"
                "Send /cancel to cancel."
            )
            return WAITING_FOR_AD_CONTENT

        photo = update.message.photo[-1]
        caption = update.message.caption or ""

        context.user_data['scheduled_ad_content'] = {
            'file_id': photo.file_id,
            'caption': caption
        }

        # Send preview
        await update.message.reply_text("📸 **Preview of your advertisement:**")
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo.file_id,
            caption=caption if caption else "(No caption)",
            parse_mode=ParseMode.MARKDOWN
        )

        await update.message.reply_text(
            "✅ **Image saved!**\n\n"
            "**Step 4:** Set the posting interval in hours.\n"
            "How often should this ad be posted?\n\n"
            "Examples:\n"
            "• 1 = Every hour\n"
            "• 6 = Every 6 hours\n"
            "• 24 = Once per day\n"
            "• 168 = Once per week\n\n"
            "Enter a number (minimum 1):",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_AD_SCHEDULE_INTERVAL


async def handle_ad_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle posting interval input"""
    try:
        interval = int(update.message.text.strip())

        if interval < 1:
            raise ValueError("Interval must be at least 1 hour")

        context.user_data['scheduled_ad_interval'] = interval

        # Get list of groups from user_usage.json
        tracker = UserUsageTracker()
        groups = []
        for user_id_str, user_data in tracker.data.get('users', {}).items():
            for group_id_str, group_data in user_data.get('groups', {}).items():
                if group_id_str not in [str(g['id']) for g in groups]:
                    groups.append({
                        'id': int(group_id_str),
                        'name': group_data.get('name', f'Group {group_id_str}')
                    })

        if not groups:
            await update.message.reply_text(
                "⚠️ **No groups found!**\n\n"
                "The bot needs to be added to at least one group first.\n"
                "Add the bot to groups, then try creating an ad again.\n\n"
                "Advertisement creation cancelled.",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data.clear()
            return ConversationHandler.END

        context.user_data['available_groups'] = groups

        # Create keyboard with groups
        keyboard = []
        for group in groups:
            keyboard.append([InlineKeyboardButton(
                f"{'✅' if group['id'] in context.user_data.get('selected_groups', []) else '☐'} {group['name']}",
                callback_data=f"selectgroup_{group['id']}"
            )])
        keyboard.append([InlineKeyboardButton("✅ Done (Select at least 1)", callback_data="selectgroup_done")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="selectgroup_cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ **Interval: Every {interval} hour(s)**\n\n"
            "**Step 5:** Select target groups for this advertisement.\n"
            "Click on groups to select/deselect them:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_AD_GROUP_SELECTION

    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a valid number (minimum 1).\n\n"
            "Send /cancel to cancel."
        )
        return WAITING_FOR_AD_SCHEDULE_INTERVAL


async def handle_group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group selection for ad targeting"""
    query = update.callback_query
    await query.answer()

    if query.data == "selectgroup_cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Advertisement creation cancelled.")
        return ConversationHandler.END

    if query.data == "selectgroup_done":
        selected_groups = context.user_data.get('selected_groups', [])

        if not selected_groups:
            await query.answer("⚠️ Please select at least one group!", show_alert=True)
            return WAITING_FOR_AD_GROUP_SELECTION

        # Create the scheduled ad
        name = context.user_data['scheduled_ad_name']
        ad_type = context.user_data['scheduled_ad_type']
        content = context.user_data['scheduled_ad_content']
        interval = context.user_data['scheduled_ad_interval']

        ad_id = ad_scheduler.create_ad(
            name=name,
            ad_type=ad_type,
            content=content,
            interval_hours=interval,
            target_groups=selected_groups,
            enabled=True
        )

        group_names = [g['name'] for g in context.user_data['available_groups'] if g['id'] in selected_groups]

        await query.edit_message_text(
            f"✅ **Scheduled Advertisement Created!**\n\n"
            f"**ID:** `{ad_id}`\n"
            f"**Name:** {name}\n"
            f"**Type:** {ad_type.capitalize()}\n"
            f"**Interval:** Every {interval} hour(s)\n"
            f"**Target Groups:** {len(selected_groups)}\n"
            f"  - {', '.join(group_names)}\n\n"
            f"The advertisement will start posting automatically!\n\n"
            f"**Management Commands:**\n"
            f"• /listads - View all ads\n"
            f"• /pausead - Pause an ad\n"
            f"• /resumead - Resume an ad\n"
            f"• /editad - Edit an ad\n"
            f"• /deletead - Delete an ad",
            parse_mode=ParseMode.MARKDOWN
        )

        context.user_data.clear()
        return ConversationHandler.END

    # Toggle group selection
    if query.data.startswith("selectgroup_"):
        group_id = int(query.data.replace("selectgroup_", ""))
        selected_groups = context.user_data.get('selected_groups', [])

        if group_id in selected_groups:
            selected_groups.remove(group_id)
        else:
            selected_groups.append(group_id)

        context.user_data['selected_groups'] = selected_groups

        # Update keyboard
        groups = context.user_data['available_groups']
        keyboard = []
        for group in groups:
            keyboard.append([InlineKeyboardButton(
                f"{'✅' if group['id'] in selected_groups else '☐'} {group['name']}",
                callback_data=f"selectgroup_{group['id']}"
            )])
        keyboard.append([InlineKeyboardButton("✅ Done (Select at least 1)", callback_data="selectgroup_done")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="selectgroup_cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except:
            pass  # Message not modified

        return WAITING_FOR_AD_GROUP_SELECTION


async def listads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all scheduled advertisements (Owner only)"""
    if not await owner_only(update, context):
        return

    ads = ad_scheduler.get_all_ads()

    if not ads:
        await update.message.reply_text(
            "📭 **No Scheduled Advertisements**\n\n"
            "You haven't created any scheduled ads yet.\n\n"
            "Use /createad to create your first scheduled advertisement!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    message = "📋 **Scheduled Advertisements**\n\n"

    for ad_id, ad_data in ads.items():
        status = "🟢 Active" if ad_data.get('enabled') else "🔴 Paused"
        last_posted = ad_data.get('last_posted_at')
        if last_posted:
            last_posted_time = datetime.fromisoformat(last_posted)
            last_posted_str = last_posted_time.strftime("%Y-%m-%d %H:%M")
        else:
            last_posted_str = "Never"

        message += (
            f"**{ad_data['name']}** {status}\n"
            f"  ID: `{ad_id}`\n"
            f"  Type: {ad_data['type'].capitalize()}\n"
            f"  Interval: Every {ad_data['interval_hours']}h\n"
            f"  Groups: {len(ad_data.get('target_groups', []))}\n"
            f"  Posted: {ad_data.get('total_posts', 0)} times\n"
            f"  Last: {last_posted_str}\n\n"
        )

    message += (
        "**Commands:**\n"
        "• /pausead `<id>` - Pause ad\n"
        "• /resumead `<id>` - Resume ad\n"
        "• /deletead `<id>` - Delete ad\n"
        "• /editad `<id>` - Edit ad"
    )

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def pausead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause a scheduled advertisement (Owner only)"""
    if not await owner_only(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ **Usage:** `/pausead <ad_id>`\n\n"
            "Use /listads to see all advertisement IDs.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    ad_id = context.args[0]
    ad = ad_scheduler.get_ad(ad_id)

    if not ad:
        await update.message.reply_text(
            f"❌ Advertisement `{ad_id}` not found.\n\n"
            "Use /listads to see all advertisements.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not ad.get('enabled'):
        await update.message.reply_text(
            f"ℹ️ Advertisement **{ad['name']}** is already paused.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    ad_scheduler.pause_ad(ad_id)

    await update.message.reply_text(
        f"⏸️ **Advertisement Paused**\n\n"
        f"**Name:** {ad['name']}\n"
        f"**ID:** `{ad_id}`\n\n"
        f"The advertisement will not be posted until you resume it.\n\n"
        f"Use `/resumead {ad_id}` to resume posting.",
        parse_mode=ParseMode.MARKDOWN
    )


async def resumead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume a paused advertisement (Owner only)"""
    if not await owner_only(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ **Usage:** `/resumead <ad_id>`\n\n"
            "Use /listads to see all advertisement IDs.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    ad_id = context.args[0]
    ad = ad_scheduler.get_ad(ad_id)

    if not ad:
        await update.message.reply_text(
            f"❌ Advertisement `{ad_id}` not found.\n\n"
            "Use /listads to see all advertisements.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if ad.get('enabled'):
        await update.message.reply_text(
            f"ℹ️ Advertisement **{ad['name']}** is already active.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    ad_scheduler.resume_ad(ad_id)

    await update.message.reply_text(
        f"▶️ **Advertisement Resumed**\n\n"
        f"**Name:** {ad['name']}\n"
        f"**ID:** `{ad_id}`\n\n"
        f"The advertisement will resume posting according to its schedule.",
        parse_mode=ParseMode.MARKDOWN
    )


async def deletead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a scheduled advertisement (Owner only)"""
    if not await owner_only(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ **Usage:** `/deletead <ad_id>`\n\n"
            "Use /listads to see all advertisement IDs.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    ad_id = context.args[0]
    ad = ad_scheduler.get_ad(ad_id)

    if not ad:
        await update.message.reply_text(
            f"❌ Advertisement `{ad_id}` not found.\n\n"
            "Use /listads to see all advertisements.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Create confirmation keyboard
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"deleteconfirm_{ad_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="deletecancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⚠️ **Confirm Deletion**\n\n"
        f"Are you sure you want to delete this advertisement?\n\n"
        f"**Name:** {ad['name']}\n"
        f"**ID:** `{ad_id}`\n"
        f"**Posted:** {ad.get('total_posts', 0)} times\n\n"
        f"This action cannot be undone!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle delete confirmation"""
    query = update.callback_query
    await query.answer()

    if query.data == "deletecancel":
        await query.edit_message_text("❌ Deletion cancelled.")
        return

    if query.data.startswith("deleteconfirm_"):
        ad_id = query.data.replace("deleteconfirm_", "")
        ad = ad_scheduler.get_ad(ad_id)

        if not ad:
            await query.edit_message_text(
                f"❌ Advertisement not found. It may have been already deleted."
            )
            return

        ad_name = ad['name']
        ad_scheduler.delete_ad(ad_id)

        await query.edit_message_text(
            f"🗑️ **Advertisement Deleted**\n\n"
            f"**Name:** {ad_name}\n"
            f"**ID:** `{ad_id}`\n\n"
            f"The advertisement has been permanently deleted.",
            parse_mode=ParseMode.MARKDOWN
        )


async def cancel_scheduled_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel scheduled ad creation"""
    context.user_data.clear()
    await update.message.reply_text("❌ Advertisement creation cancelled.")
    return ConversationHandler.END


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user questions (text only) with AI response"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    question = update.message.text

    # Track this chat for broadcasting
    chat = update.effective_chat
    usage_tracker.track_chat(chat.id, chat.type, chat.title)

    # In group chats, only respond if bot is mentioned
    if not is_bot_mentioned(update, context):
        logger.info(f"[BOT] Ignoring message in group {chat.id} - bot not mentioned")
        return

    # Skip AI processing if owner has disabled AI mode
    global OWNER_AI_ENABLED
    if is_owner(user_id) and not OWNER_AI_ENABLED:
        logger.info(f"[BOT] Skipping AI response for owner - AI mode disabled")
        return

    # Check if user has enough credits (Owner bypass - owner has unlimited access)
    if not is_owner(user_id):
        if not usage_tracker.can_ask_question(user_id, is_image=False):
            credits = usage_tracker.get_credits(user_id)
            daily_usage = usage_tracker.get_daily_usage(user_id)
            daily_limit = usage_tracker.DAILY_CREDIT_LIMIT

            # Check if it's a daily limit issue or credit issue
            if daily_usage >= daily_limit:
                limit_message = (
                    "⏰ **Daily Limit Reached!**\n\n"
                    f"📊 You've used **{daily_usage}/{daily_limit} credits** today.\n"
                    f"⏱️ Your limit will reset tomorrow.\n\n"
                    "💡 **Why daily limits?**\n"
                    "To ensure fair usage for all users.\n\n"
                    f"📱 Want unlimited access? Download Nova Learn App:\n{NOVA_LEARN_APP_LINK}\n\n"
                    "Get:\n"
                    "✨ Unlimited AI-powered answers\n"
                    "✨ Advanced learning features\n"
                    "✨ Personalized study plans\n"
                    "✨ And much more!\n\n"
                    f"📢 Join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}"
                )
            else:
                limit_message = (
                    "⚠️ **Insufficient Credits!**\n\n"
                    f"💰 Your Balance: **{credits} credits**\n"
                    f"💳 Required: **{usage_tracker.TEXT_QUESTION_COST} credit**\n"
                    f"📊 Daily Usage: **{daily_usage}/{daily_limit} credits**\n\n"
                    "🚀 Get more credits:\n\n"
                    "Use /credits to see available packages\n\n"
                    f"📱 Or download Nova Learn App for unlimited access:\n{NOVA_LEARN_APP_LINK}\n\n"
                    "Get:\n"
                    "✨ Unlimited AI-powered answers\n"
                    "✨ Advanced learning features\n"
                    "✨ Personalized study plans\n"
                    "✨ And much more!\n\n"
                    f"📢 Join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}"
                )
            reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
            await update.message.reply_text(limit_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            return

    # Send "typing" action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Send "please wait" message
    wait_message = await update.message.reply_text(
        "⏳ Processing your question...\n\n"
        "🤖 AI is analyzing and preparing a detailed answer.\n"
        "⏱️ This may take 30-90 seconds.\n\n"
        "Please wait..."
    )

    try:
        logger.info(f"[BOT] Text question from user {user_id}: {question[:100]}...")

        # Get AI response with fallback chain (no image)
        message_length = len(question)
        ai_response, metadata = await get_ai_response(question, message_length, None)

        if not ai_response or not ai_response.strip():
            raise Exception("Received empty response from AI")

        logger.info(f"[BOT] Got response: {len(ai_response)} chars, model: {metadata.get('model')}")

        # Record the question and deduct credits (skip for owner)
        if not is_owner(user_id):
            usage_tracker.record_question(user_id, username, is_image=False)
            remaining_credits = usage_tracker.get_credits(user_id)
            logger.info(f"[CREDITS] User {user_id} has {remaining_credits} credits remaining")

        # Convert LaTeX to Unicode plain text
        formatted_response = convert_latex_to_telegram(ai_response)

        # Add footer with credit info
        if is_owner(user_id):
            footer = (
                "\n\n━━━━━━━━━━━━━━━━━━\n"
                "🤖 Powered by NovaAI\n"
                "👑 Owner Access - Unlimited"
            )
        else:
            remaining_credits = usage_tracker.get_credits(user_id)
            footer = (
                "\n\n━━━━━━━━━━━━━━━━━━\n"
                "🤖 Powered by NovaAI\n"
                f"💰 Credits Used: {usage_tracker.TEXT_QUESTION_COST} | Remaining: {remaining_credits}\n"
                f"📱 Get more: /credits or {NOVA_LEARN_APP_LINK}"
            )

        full_response = formatted_response + footer

        # Split long messages (Telegram limit: 4096 chars)
        MAX_MESSAGE_LENGTH = 4000

        if len(full_response) <= MAX_MESSAGE_LENGTH:
            # Send as single message (plain text - no markdown parsing needed)
            await update.message.reply_text(full_response)
        else:
            # Split into multiple messages
            parts = []
            current_part = ""

            for line in full_response.split('\n'):
                if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += ("\n" if current_part else "") + line

            if current_part:
                parts.append(current_part)

            # Send parts
            for i, part in enumerate(parts):
                # Only add footer to last part
                if i == len(parts) - 1:
                    await update.message.reply_text(part + footer)
                else:
                    await update.message.reply_text(part)

                # Small delay between messages
                if i < len(parts) - 1:
                    await asyncio.sleep(0.5)

        logger.info(f"[BOT] ✅ Response sent successfully to user {user_id}")

        # Send advertisement after successful response
        await send_advertisement(update, context)

        # Show keyboard again in private chats
        if update.effective_chat.type == 'private':
            keyboard_message = "💡 Use the buttons below for quick access:"
            await update.message.reply_text(keyboard_message, reply_markup=get_main_keyboard(update.effective_user.id))

    except Exception as e:
        logger.error(f"[BOT] Error processing question: {e}", exc_info=True)
        error_message = (
            "❌ Sorry, I encountered an error processing your question.\n\n"
            "This could be due to:\n"
            "• High server load\n"
            "• Complex question requiring more processing\n"
            "• Temporary API issues\n\n"
            "Please try:\n"
            "• Simplifying your question\n"
            "• Trying again in a few moments\n\n"
            f"📱 For unlimited access and priority support:\n{NOVA_LEARN_APP_LINK}\n\n"
            f"📢 Join our WhatsApp channel: {WHATSAPP_CHANNEL_LINK}"
        )
        # Show keyboard in error message too
        reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
        await update.message.reply_text(error_message, reply_markup=reply_markup)


async def handle_photo_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle questions with images"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # Track this chat for broadcasting
    chat = update.effective_chat
    usage_tracker.track_chat(chat.id, chat.type, chat.title)

    # Get caption as the question, or use default
    question = update.message.caption or "Please analyze this image and explain what you see. If it's a problem, solve it. If it's a diagram, explain it."

    # If caption starts with #broadcast, it should be handled by broadcast handler
    # This is a safety check in case the handler didn't catch it
    if question.startswith("#broadcast"):
        if is_owner(user_id):
            await update.message.reply_text(
                "⚠️ **Broadcast Format Error**\n\n"
                "Make sure your caption starts with:\n"
                "`#broadcast all <message>`\n"
                "`#broadcast users <message>`\n"
                "`#broadcast groups <message>`\n\n"
                "Note: There must be exactly one space after 'broadcast'",
                parse_mode=ParseMode.MARKDOWN
            )
        return  # Don't process as a question

    # In group chats, only respond if bot is mentioned
    if not is_bot_mentioned(update, context):
        logger.info(f"[BOT] Ignoring photo in group {chat.id} - bot not mentioned")
        # Send a helpful message to guide users (only occasionally to avoid spam)
        if random.random() < 0.3:  # 30% chance to show hint
            bot_username = context.bot.username
            hint_message = (
                f"💡 **Tip:** To ask about this image, mention me in the caption!\n\n"
                f"Example: `@{bot_username} What is this?`\n\n"
                f"Or reply to one of my messages with your photo."
            )
            await update.message.reply_text(hint_message, parse_mode=ParseMode.MARKDOWN)
        return

    # Skip AI processing if owner has disabled AI mode
    global OWNER_AI_ENABLED
    if is_owner(user_id) and not OWNER_AI_ENABLED:
        logger.info(f"[BOT] Skipping AI response for owner photo - AI mode disabled")
        return

    # Check if user has enough credits (Owner bypass - owner has unlimited access)
    if not is_owner(user_id):
        if not usage_tracker.can_ask_question(user_id, is_image=True):
            credits = usage_tracker.get_credits(user_id)
            daily_usage = usage_tracker.get_daily_usage(user_id)
            daily_limit = usage_tracker.DAILY_CREDIT_LIMIT

            # Check if it's a daily limit issue or credit issue
            if daily_usage >= daily_limit:
                limit_message = (
                    "⏰ **Daily Limit Reached!**\n\n"
                    f"📊 You've used **{daily_usage}/{daily_limit} credits** today.\n"
                    f"⏱️ Your limit will reset tomorrow.\n\n"
                    "💡 **Why daily limits?**\n"
                    "To ensure fair usage for all users.\n\n"
                    f"📱 Want unlimited access? Download Nova Learn App:\n{NOVA_LEARN_APP_LINK}\n\n"
                    "Get:\n"
                    "✨ Unlimited AI-powered answers\n"
                    "✨ Advanced learning features\n"
                    "✨ Personalized study plans\n"
                    "✨ And much more!\n\n"
                    f"📢 Join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}"
                )
            else:
                limit_message = (
                    "⚠️ **Insufficient Credits!**\n\n"
                    f"💰 Your Balance: **{credits} credits**\n"
                    f"💳 Required: **{usage_tracker.IMAGE_QUESTION_COST} credits**\n"
                    f"📊 Daily Usage: **{daily_usage}/{daily_limit} credits**\n\n"
                    "📸 Image questions cost more due to higher processing requirements.\n\n"
                    "🚀 Get more credits:\n\n"
                    "Use /credits to see available packages\n\n"
                    f"📱 Or download Nova Learn App for unlimited access:\n{NOVA_LEARN_APP_LINK}\n\n"
                    "Get:\n"
                    "✨ Unlimited AI-powered answers\n"
                    "✨ Advanced learning features\n"
                    "✨ Personalized study plans\n"
                    "✨ And much more!\n\n"
                    f"📢 Join our WhatsApp channel:\n{WHATSAPP_CHANNEL_LINK}"
                )
            reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
            await update.message.reply_text(limit_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            return

    # Send "typing" action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Send "please wait" message for image analysis
    wait_message = await update.message.reply_text(
        "⏳ Processing your image...\n\n"
        "🤖 AI is analyzing the image and preparing a detailed answer.\n"
        "⏱️ Image analysis may take 2-5 minutes.\n\n"
        "Please wait..."
    )

    try:
        logger.info(f"[BOT] Photo question from user {user_id}: {question[:100]}...")

        # Get the largest photo (best quality)
        photo = update.message.photo[-1]

        # Process the image
        try:
            base64_image, mime_type = await process_telegram_photo(photo, context)
            image_data = (base64_image, mime_type)
            logger.info(f"[BOT] Image processed successfully")
        except ValueError as ve:
            # Image too large
            error_message = (
                "❌ Image Too Large!\n\n"
                f"{str(ve)}\n\n"
                "Please:\n"
                "• Crop the image to focus on the important part\n"
                "• Compress the image\n"
                "• Try a lower resolution\n\n"
                "Maximum size: 5MB"
            )
            await update.message.reply_text(error_message)
            return
        except Exception as e:
            logger.error(f"[BOT] Image processing failed: {e}")
            error_message = (
                "❌ Failed to process image\n\n"
                "Please try:\n"
                "• Sending a different image format\n"
                "• Compressing the image\n"
                "• Trying again in a moment\n\n"
                f"Error: {str(e)}"
            )
            await update.message.reply_text(error_message)
            return

        # Get AI response with image
        message_length = len(question)
        ai_response, metadata = await get_ai_response(question, message_length, image_data)

        if not ai_response or not ai_response.strip():
            raise Exception("Received empty response from AI")

        logger.info(f"[BOT] Got response: {len(ai_response)} chars, model: {metadata.get('model')}")

        # Record the question and deduct credits (skip for owner)
        if not is_owner(user_id):
            usage_tracker.record_question(user_id, username, is_image=True)
            remaining_credits = usage_tracker.get_credits(user_id)
            logger.info(f"[CREDITS] User {user_id} has {remaining_credits} credits remaining")

        # Convert LaTeX to Unicode plain text
        formatted_response = convert_latex_to_telegram(ai_response)

        # Add footer with credit info
        if is_owner(user_id):
            footer = (
                "\n\n━━━━━━━━━━━━━━━━━━\n"
                "🤖 Powered by NovaAI\n"
                "📸 Image analysis complete\n"
                "👑 Owner Access - Unlimited"
            )
        else:
            remaining_credits = usage_tracker.get_credits(user_id)
            footer = (
                "\n\n━━━━━━━━━━━━━━━━━━\n"
                "🤖 Powered by NovaAI\n"
                "📸 Image analysis complete\n"
                f"💰 Credits Used: {usage_tracker.IMAGE_QUESTION_COST} | Remaining: {remaining_credits}\n"
                f"📱 Get more: /credits or {NOVA_LEARN_APP_LINK}"
            )

        full_response = formatted_response + footer

        # Split long messages (Telegram limit: 4096 chars)
        MAX_MESSAGE_LENGTH = 4000

        if len(full_response) <= MAX_MESSAGE_LENGTH:
            # Send as single message (plain text - no markdown parsing needed)
            await update.message.reply_text(full_response)
        else:
            # Split into multiple messages
            parts = []
            current_part = ""

            for line in full_response.split('\n'):
                if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += ("\n" if current_part else "") + line

            if current_part:
                parts.append(current_part)

            # Send parts
            for i, part in enumerate(parts):
                # Only add footer to last part
                if i == len(parts) - 1:
                    await update.message.reply_text(part + footer)
                else:
                    await update.message.reply_text(part)

                # Small delay between messages
                if i < len(parts) - 1:
                    await asyncio.sleep(0.5)

        logger.info(f"[BOT] ✅ Response sent successfully to user {user_id}")

        # Send advertisement after successful response
        await send_advertisement(update, context)

        # Show keyboard again in private chats
        if update.effective_chat.type == 'private':
            keyboard_message = "💡 Use the buttons below for quick access:"
            await update.message.reply_text(keyboard_message, reply_markup=get_main_keyboard(update.effective_user.id))

    except Exception as e:
        logger.error(f"[BOT] Error processing photo question: {e}", exc_info=True)
        error_message = (
            "❌ Sorry, I encountered an error processing your image.\n\n"
            "This could be due to:\n"
            "• Image format not supported\n"
            "• High server load\n"
            "• Complex image requiring more processing\n"
            "• Temporary API issues\n\n"
            "Please try:\n"
            "• Using a clearer image\n"
            "• Adding a text caption describing what you need help with\n"
            "• Trying again in a few moments\n\n"
            f"📱 For unlimited access and priority support:\n{NOVA_LEARN_APP_LINK}\n\n"
            f"📢 Join our WhatsApp channel: {WHATSAPP_CHANNEL_LINK}"
        )
        # Show keyboard in error message too
        reply_markup = get_main_keyboard(update.effective_user.id) if update.effective_chat.type == 'private' else None
        await update.message.reply_text(error_message, reply_markup=reply_markup)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not found in environment variables!")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("credits", credits_command))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("keyboard", keyboard_command))

    # Owner-only commands
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("addcredits", addcredits_command))
    application.add_handler(CommandHandler("setcredits", setcredits_command))
    application.add_handler(CommandHandler("togglead", togglead_command))

    # Scheduled ad management commands
    application.add_handler(CommandHandler("listads", listads_command))
    application.add_handler(CommandHandler("pausead", pausead_command))
    application.add_handler(CommandHandler("resumead", resumead_command))
    application.add_handler(CommandHandler("deletead", deletead_command))

    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Advertisement configuration conversation handler (Owner only)
    ad_conv = ConversationHandler(
        entry_points=[CommandHandler('setad', setad_command)],
        states={
            WAITING_FOR_AD_IMAGE: [
                CallbackQueryHandler(handle_ad_type_selection, pattern='^adtype_'),
                MessageHandler(filters.PHOTO, handle_ad_image)
            ],
            WAITING_FOR_AD_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_caption)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_ad_config)],
    )
    application.add_handler(ad_conv)

    # Scheduled ad creation conversation handler (Owner only)
    scheduled_ad_conv = ConversationHandler(
        entry_points=[CommandHandler('createad', createad_command)],
        states={
            WAITING_FOR_AD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_name)
            ],
            WAITING_FOR_AD_TYPE_SELECT: [
                CallbackQueryHandler(handle_scheduled_ad_type, pattern='^schedtype_')
            ],
            WAITING_FOR_AD_CONTENT: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_scheduled_ad_content)
            ],
            WAITING_FOR_AD_SCHEDULE_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_interval)
            ],
            WAITING_FOR_AD_GROUP_SELECTION: [
                CallbackQueryHandler(handle_group_selection, pattern='^selectgroup_')
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_scheduled_ad)],
    )
    application.add_handler(scheduled_ad_conv)

    # Two-step image broadcast conversation handler
    broadcast_conv = ConversationHandler(
        entry_points=[
            CommandHandler('broadcastimg', start_image_broadcast),
            MessageHandler(filters.PHOTO & filters.User(user_id=int(OWNER_USER_ID)), start_image_broadcast)
        ],
        states={
            WAITING_FOR_BROADCAST_CAPTION: [
                CallbackQueryHandler(handle_broadcast_target, pattern='^bcast_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_broadcast)],
    )
    application.add_handler(broadcast_conv)

    # Callback query handler for inline keyboard buttons
    # Handle buy callbacks first, then delete confirmations, then settings callbacks
    application.add_handler(CallbackQueryHandler(handle_buy_callback, pattern='^(buy_|show_buy_menu)'))
    application.add_handler(CallbackQueryHandler(handle_delete_confirmation, pattern='^(deleteconfirm_|deletecancel)'))
    application.add_handler(CallbackQueryHandler(settings_callback_handler))

    # Handle broadcast images from owner (checked first before regular photo questions)
    # Use a more permissive filter and check inside the handler
    application.add_handler(
        MessageHandler(
            filters.PHOTO & filters.CAPTION,
            broadcast_image_handler
        ),
        group=0  # Higher priority group
    )

    # Handle photo messages (questions with images)
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo_question
        ),
        group=1  # Lower priority group
    )

    # Handle keyboard button presses (must be before general text handler)
    keyboard_filter = filters.Regex('^(💳 Credits|📊 Status|🛒 Buy Credits|❓ Help|🔗 Links|⚙️ Settings|📢 Broadcast|📺 Set Ad|🔄 Toggle Ad|🔇 Disable AI|🔊 Enable AI)$')
    application.add_handler(
        MessageHandler(
            keyboard_filter & ~filters.COMMAND,
            handle_keyboard_buttons
        ),
        group=0  # Higher priority
    )

    # Handle all text messages (questions without images)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_question
        ),
        group=1  # Lower priority
    )

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("NovaAiBot is starting...")

    # Initialize the application and start scheduler
    application.post_init = start_scheduler_task

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
