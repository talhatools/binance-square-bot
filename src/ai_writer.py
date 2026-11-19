"""AI Writer: Uses Anthropic Claude API (or diverse competitor-style templates) to generate punchy, varied Binance Square posts."""
import random
import time
import logging
import re
from typing import Optional, Dict, Any, List
import pandas as pd
from anthropic import Anthropic, APIError, RateLimitError
from src.technical_analysis import TradeSetup

logger = logging.getLogger(__name__)

CALL_TO_ACTIONS = [
    "👉 Take this trade now & let's print together! 🚀",
    "⚡ Open your position below & ride the momentum! 💰",
    "🔥 High probability setup! Enter now & hit the targets! 🎯",
    "🚀 Don't miss this entry! Trade now & secure profits! 💎",
    "👇 Perfect entry zone confirmed! Tap below to trade now! 📈",
    "👉 Execute trade on this coin now! 💰",
]

COMPETITOR_ARCHETYPES = [
    {
        "name": "ultra_short_sniper",
        "description": "Ultra-Short & Punchy Sniper Alert (under 250 characters)",
        "prompt_instruction": """
Format: Ultra-Short, urgent sniper trade call (strictly under 250 characters).
Structure:
- Attention hook: '🚀 Guys, {action} {cashtag} Now!'
- Clear levels:
  📍 Entry Current Price: {entry}
  🎯 TP1: {tp1}
  🎯 TP2: {tp2}
  🛑 Stop Loss: {sl}
- Closing: '👉 Execute trade on {cashtag} now! 💰'
Keep it ultra-concise and laser-focused for quick mobile traders.
""",
    },
    {
        "name": "exhaustion_danger_zone",
        "description": "Danger Zone & Liquidity Trap Breakdown (400-520 characters)",
        "prompt_instruction": """
Format: Market Structure & Liquidity Trap Breakdown (400-520 characters).
Structure:
- Strong hook: '{cashtag} IS ENTERING THE CRITICAL DANGER ZONE ... WATCHING FOR THE UNWIND'
- Stance: 'I’m looking for a BIG {direction} on {cashtag} around this area.'
- Levels: Entry Zone, TP1, TP2, Final Target (TP3), and Stop Loss.
- Rationale: Explain that after a vertical move, price is stretched at key level ({key_level}), RSI ({rsi_1h:.1f}) shows exhaustion, and liquidity is sitting on the other side.
- Closing: 'Trade on {cashtag} here 👇'
""",
    },
    {
        "name": "technical_multi_tp",
        "description": "Technical Multi-Timeframe Breakdown with Percentage Targets (450-550 characters)",
        "prompt_instruction": """
Format: Disciplined Multi-Timeframe Technical Breakdown with Percentage Targets (450-550 characters).
Structure:
- 1H/4H trend summary: '{base_asset} is reacting at key structure on the 1H/4H chart.'
- Bias: '🔴 {direction} {cashtag} /USDT (Bias: {bias}, R:R {risk_reward:.1f})'
- Levels with estimated % moves: Entry Zone, TP1, TP2, TP3, SL.
- Technical bullet points: Price vs MA20 ({ma20_1h:.4f}) and 1H RSI ({rsi_1h:.1f}).
- Action plan: Take partial profit at TP1, then trail SL to breakeven.
- Closing: '👇 Tap below to execute trade on {cashtag}!'
""",
    },
    {
        "name": "conversational_community_hook",
        "description": "Conversational Community Story Hook & Question (380-480 characters)",
        "prompt_instruction": """
Format: Conversational Community Story Hook (380-480 characters).
Structure:
- Question hook: 'guys, have you seen what’s happening with {cashtag} ? 🚨'
- Observation: Relatable summary of the sharp price move and why momentum is stalling/turning.
- Trade setup: Entry Zone, Stop Loss, and Targets (TP1 ➔ TP2 ➔ TP3).
- Community question + action CTA: 'Are the {opponents} running out of fuel or will they surprise us? 👇 Trade {cashtag} below! 🔥'
""",
    },
    {
        "name": "clean_trading_idea",
        "description": "Clean High-Impact Trading Idea with Widget CTA (240-340 characters)",
        "prompt_instruction": """
Format: Clean High-Impact Trading Idea (240-340 characters).
Structure:
- Headline: '{cashtag} BIG {direction} : [Reason why key reaction triggers next explosive move]'
- Setup:
  Trading Setup {direction} {cashtag}:
  📍 Entry: {entry_low} - {entry_high}
  🛑 SL: {sl}
  🎯 TP1: {tp1}
  🎯 TP2: {tp2}
  🎯 TP3: {tp3}
- Direct trade link/widget CTA: 'Trade {cashtag} here :👇'
""",
    },
    {
        "name": "whale_trap_thesis",
        "description": "Whale Order Book Trap Conviction (280-380 characters)",
        "prompt_instruction": """
Format: Whale / Big Player Manipulation Thesis (280-380 characters).
Structure:
- Opening: '{cashtag} The harder they push into key levels, the harder the reversal! That’s how big players trap late retail before the real trend expansion.'
- Setup: Entry Zone, TP Target, Stop Loss with R:R.
- Conviction CTA: 'Don't fight the smart money. Just go {direction_lower} on {cashtag} and lock in gains! ⚡'
""",
    },
    {
        "name": "big_reversal_recovery",
        "description": "Big Reversal / Bounce Conviction Setup (350-460 characters)",
        "prompt_instruction": """
Format: Contrarian / Reversal Conviction Setup (350-460 characters).
Structure:
- High conviction opening: 'I’m going to open a BIG {direction} on {cashtag} here.'
- Levels: Entry Zone, Target, Stop Loss.
- Market thesis: 'Look at the chart after that heavy move: {cashtag} is finally holding structure instead of breaking down. The flush already happened—now let's catch the recovery wave with 1:{risk_reward:.1f} R:R.'
- Closing: 'Trade {cashtag} now! 🚀'
""",
    },
]


POST_STYLE_ARCHETYPE_MAP = {
    "sniper": "ultra_short_sniper",
    "danger_zone": "exhaustion_danger_zone",
    "technical": "technical_multi_tp",
    "conversational": "conversational_community_hook",
    "clean": "clean_trading_idea",
    "whale": "whale_trap_thesis",
    "reversal": "big_reversal_recovery",
}


def normalize_post_style(style_str: Optional[str]) -> str:
    """Normalizes user/config post style input to canonical archetype key."""
    s = (style_str or "auto").strip().lower().replace("-", "_").replace(" ", "_")
    if s in ("sniper", "short", "ultra_short", "fast", "ultra_short_sniper"):
        return "sniper"
    if s in ("danger_zone", "danger", "trap", "breakdown", "exhaustion", "exhaustion_danger_zone"):
        return "danger_zone"
    if s in ("technical", "tech", "multi_tp", "indicator", "technical_multi_tp"):
        return "technical"
    if s in ("conversational", "community", "question", "story", "conversational_community_hook"):
        return "conversational"
    if s in ("clean", "idea", "trading_idea", "simple", "clean_trading_idea"):
        return "clean"
    if s in ("whale", "smart_money", "order_book", "whale_trap_thesis"):
        return "whale"
    if s in ("reversal", "bounce", "recovery", "contrarian", "big_reversal_recovery"):
        return "reversal"
    return "auto"


def format_price(val: float) -> str:
    """Formats numeric crypto prices dynamically based on magnitude."""
    if val >= 1000:
        return f"${val:,.1f}" if val % 1 != 0 else f"${int(val):,}"
    elif val >= 100:
        return f"${val:.2f}"
    elif val >= 1:
        return f"{val:.4f}".rstrip("0").rstrip(".") if len(f"{val:.4f}") > 7 else f"{val:.4f}"
    elif val >= 0.01:
        return f"{val:.5f}"
    else:
        return f"{val:.6f}"


class AIWriter:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_retries: int = 3,
        retry_delay_base: float = 2.0,
        disable_api: bool = False,
        default_post_style: str = "auto",
    ):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.disable_api = disable_api
        self.default_post_style = default_post_style
        self.client = Anthropic(api_key=api_key) if (api_key and not disable_api) else None

    def _calculate_laddered_targets(self, setup: TradeSetup) -> Dict[str, float]:
        """Calculates multi-target levels (TP1, TP2, TP3) and percentage changes."""
        curr = setup.current_price
        target = setup.target_price
        sl = setup.stop_loss
        is_long = setup.direction == "LONG"

        if is_long:
            diff = max(target - curr, curr * 0.015)
            tp1 = curr + diff * 0.40
            tp2 = curr + diff * 0.75
            tp3 = target
            pct_tp1 = ((tp1 - curr) / curr) * 100
            pct_tp2 = ((tp2 - curr) / curr) * 100
            pct_tp3 = ((tp3 - curr) / curr) * 100
            pct_sl = ((curr - sl) / curr) * 100
        else:
            diff = max(curr - target, curr * 0.015)
            tp1 = curr - diff * 0.40
            tp2 = curr - diff * 0.75
            tp3 = target
            pct_tp1 = ((curr - tp1) / curr) * 100
            pct_tp2 = ((curr - tp2) / curr) * 100
            pct_tp3 = ((curr - tp3) / curr) * 100
            pct_sl = ((sl - curr) / curr) * 100

        return {
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "pct_tp1": abs(pct_tp1),
            "pct_tp2": abs(pct_tp2),
            "pct_tp3": abs(pct_tp3),
            "pct_sl": abs(pct_sl),
        }

    def generate_post_text(self, setup: TradeSetup, post_style: Optional[str] = None) -> str:
        """
        Generates a Binance Square post dynamically styled after top-performing
        competitors (ranging from ultra-short sniper calls to detailed technical multi-TPs).
        Allows choosing a specific post style or auto-rotating.
        """
        base_asset = setup.coin.replace("USDT", "")
        cashtag = f"${base_asset}"
        bias = "Bullish" if setup.direction == "LONG" else "Bearish"
        chosen_style = normalize_post_style(post_style or self.default_post_style)

        # If Claude API is disabled or not configured, generate competitor template (free)
        if self.disable_api or not self.client or not self.api_key or self.api_key.startswith("your_"):
            logger.info(f"Using competitor template generator (style: {chosen_style}, free mode).")
            return self._generate_template_fallback(setup, cashtag, bias, post_style=chosen_style)

        prompt = self._build_prompt(setup, cashtag, bias, post_style=chosen_style)

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Calling Anthropic API ({self.model}, style: {chosen_style}) - Attempt {attempt + 1}")
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )

                response_text = message.content[0].text.strip()
                # Enforce no disclaimers, proper trade CTA, and character limit
                response_text = self._enforce_length_and_cta(response_text)

                logger.info(f"Generated AI post ({len(response_text)} chars, style: {chosen_style}):\n{response_text}")
                return response_text

            except RateLimitError as exc:
                delay = self.retry_delay_base * (2 ** attempt) + random.uniform(1.0, 3.0)
                logger.warning(f"Claude API rate limit hit: {exc}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
            except (APIError, Exception) as exc:
                delay = self.retry_delay_base * (2 ** attempt)
                logger.warning(f"Claude API error: {exc}. Retrying in {delay:.1f}s...")
                time.sleep(delay)

        logger.error("Claude API retries exhausted. Falling back to template text.")
        return self._generate_template_fallback(setup, cashtag, bias, post_style=chosen_style)

    def _build_prompt(self, setup: TradeSetup, cashtag: str, bias: str, post_style: str = "auto") -> str:
        base_asset = setup.coin.replace("USDT", "")
        action = "LONG" if setup.direction == "LONG" else "SHORT"
        targets = self._calculate_laddered_targets(setup)

        archetype_name = POST_STYLE_ARCHETYPE_MAP.get(post_style)
        archetype = None
        if archetype_name:
            archetype = next((a for a in COMPETITOR_ARCHETYPES if a["name"] == archetype_name), None)
        if not archetype:
            archetype = random.choice(COMPETITOR_ARCHETYPES)

        reasons_bullet = "\n- ".join(setup.reasons)

        instruction = archetype["prompt_instruction"].format(
            action=action,
            direction=setup.direction,
            direction_lower=setup.direction.lower(),
            cashtag=cashtag,
            base_asset=base_asset,
            bias=bias,
            entry=format_price(setup.current_price),
            entry_low=format_price(setup.entry_low),
            entry_high=format_price(setup.entry_high),
            tp1=format_price(targets["tp1"]),
            tp2=format_price(targets["tp2"]),
            tp3=format_price(targets["tp3"]),
            sl=format_price(setup.stop_loss),
            risk_reward=setup.risk_reward,
            rsi_1h=setup.rsi_1h,
            ma20_1h=setup.ma20_1h,
            key_level=format_price(setup.support_level if setup.direction == "LONG" else setup.resistance_level),
            opponents="bears" if setup.direction == "LONG" else "bulls",
        )

        return f"""
You are a top-tier crypto trader and influencer on Binance Square.
Your objective is to write an authentic, high-converting post about {cashtag} that builds immediate trust and motivates followers to execute the trade directly through this post.

Technical Data:
- Coin: {cashtag} ({setup.coin})
- Bias: {bias} ({setup.direction})
- Current Price: {format_price(setup.current_price)}
- Entry Zone: {format_price(setup.entry_low)} - {format_price(setup.entry_high)}
- TP1: {format_price(targets['tp1'])} | TP2: {format_price(targets['tp2'])} | Final TP: {format_price(targets['tp3'])}
- Stop Loss: {format_price(setup.stop_loss)}
- Risk/Reward: 1:{setup.risk_reward:.1f}
- 1H RSI: {setup.rsi_1h:.1f} | 1H MA20: {setup.ma20_1h:.4f}
- Primary Reasons:
  - {reasons_bullet}

Style & Format Requirements:
{instruction}

Strict Rules:
1. MAXIMUM 560 characters. Mobile-friendly, high engagement.
2. Include cashtag {cashtag} prominently.
3. Absolutely DO NOT include any disclaimer, "Not financial advice", "NFA", or "DYOR".
4. Make sure the post ends with a clear, strong trade Call-to-Action (CTA) encouraging readers to trade now.
"""

    def _clean_disclaimers(self, text: str) -> str:
        """Removes any variation of 'Not financial advice', 'NFA', 'DYOR', etc."""
        disclaimer_patterns = [
            r"(?i)\bthis\s+is\s+not\s+financial\s+advice\.?",
            r"(?i)\bnot\s+financial\s+advice\.?",
            r"(?i)\bnfa\.?",
            r"(?i)\bdyor\.?",
            r"(?i)\bdo\s+your\s+own\s+research\.?",
            r"(?i)\bpersonal\s+market\s+analysis\s+only\.?",
            r"(?i)\beducational\s+content,\s+not\s+investment\s+advice\.?",
        ]
        for pat in disclaimer_patterns:
            text = re.sub(pat, "", text)

        lines = [line.strip() for line in text.split("\n")]
        cleaned_lines = []
        for line in lines:
            if line or (cleaned_lines and cleaned_lines[-1] != ""):
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    def _enforce_length_and_cta(self, text: str, cta: Optional[str] = None) -> str:
        """Strips disclaimers, ensures an actionable trade CTA is present, and caps length at 600 chars."""
        text = self._clean_disclaimers(text)
        chosen_cta = cta or random.choice(CALL_TO_ACTIONS)

        # Check if text already has a strong trade CTA
        has_cta = any(
            phrase in text.lower()
            for phrase in [
                "trade now", "trade on", "trade here", "trade below",
                "open your", "take this trade", "tap below", "let's print",
                "execute trade", "go short", "go long", "lock in gains"
            ]
        )
        if not has_cta:
            text = f"{text}\n\n{chosen_cta}"

        # Enforce max length constraint (600 characters)
        if len(text) > 600:
            cta_suffix = f"\n\n{chosen_cta}"
            max_body_len = 600 - len(cta_suffix)
            if max_body_len > 100:
                text = text[:max_body_len].rsplit(" ", 1)[0] + cta_suffix
            else:
                text = text[:600]

        return text

    def _enforce_length_and_disclaimer(self, text: str) -> str:
        """Backwards compatibility alias for _enforce_length_and_cta without disclaimers."""
        return self._enforce_length_and_cta(text)

    def _generate_template_fallback(
        self,
        setup: TradeSetup,
        cashtag: str,
        bias: str,
        post_style: str = "auto",
    ) -> str:
        """
        Deterministic template generator modeled directly on real high-performing competitor posts.
        Returns the chosen post_style template, or picks a varied template if post_style is 'auto'.
        """
        base_asset = setup.coin.replace("USDT", "")
        direction = setup.direction
        action = "LONG" if direction == "LONG" else "SHORT"
        targets = self._calculate_laddered_targets(setup)

        f_curr = format_price(setup.current_price)
        f_entry_low = format_price(setup.entry_low)
        f_entry_high = format_price(setup.entry_high)
        f_tp1 = format_price(targets["tp1"])
        f_tp2 = format_price(targets["tp2"])
        f_tp3 = format_price(targets["tp3"])
        f_sl = format_price(setup.stop_loss)
        f_ma20 = format_price(setup.ma20_1h)

        key_level_val = setup.support_level if direction == "LONG" else setup.resistance_level
        f_key_level = format_price(key_level_val)
        level_type = "support" if direction == "LONG" else "resistance"
        opponents = "bears" if direction == "LONG" else "bulls"

        templates_map = {
            # 1. Ultra-Short / Fast Sniper Alert (under 250 chars)
            "sniper": (
                f"🚀 Guys, {action} {cashtag} Now!\n\n"
                f"📍 Entry Current Price: {f_curr}\n\n"
                f"🎯 TP1: {f_tp1}\n"
                f"🎯 TP2: {f_tp2}\n\n"
                f"🛑 Stop Loss: {f_sl}\n\n"
                f"👉 Execute trade on {cashtag} now! 💰"
            ),
            # 2. Danger Zone / Liquidity Trap Breakdown
            "danger_zone": (
                f"{cashtag} IS ENTERING THE CRITICAL DANGER ZONE ... WATCHING FOR THE UNWIND\n\n"
                f"I’m looking for a BIG {direction.upper()} on {cashtag} around this area.\n\n"
                f"📍 Entry: {f_entry_low} - {f_entry_high}\n"
                f"🎯 TP1: {f_tp1}\n"
                f"🎯 TP2: {f_tp2}\n"
                f"🎯 Final Target: {f_tp3}\n"
                f"🛑 SL: {f_sl}\n\n"
                f"Why {direction.lower()} here? Price is stretched at {level_type} ({f_key_level}) after an aggressive {'dump' if direction == 'LONG' else 'pump'}. "
                f"1H RSI ({setup.rsi_1h:.1f}) signals {'seller' if direction == 'LONG' else 'buyer'} exhaustion while liquidity sits {'higher' if direction == 'LONG' else 'lower'}.\n\n"
                f"Trade on {cashtag} here 👇"
            ),
            # 3. Technical Multi-Target Breakdown with % and indicators
            "technical": (
                f"{base_asset} is reacting at key structure on the 1H/4H chart.\n\n"
                f"{'🔴 SHORT' if direction == 'SHORT' else '🟢 LONG'} {cashtag} /USDT\n"
                f"Bias: {bias.upper()} · R:R {setup.risk_reward:.1f}\n\n"
                f"📍 Entry: {f_entry_low} – {f_entry_high}\n"
                f"🎯 TP1: {f_tp1} ({targets['pct_tp1']:.1f}%)\n"
                f"🎯 TP2: {f_tp2} ({targets['pct_tp2']:.1f}%)\n"
                f"🎯 TP3: {f_tp3} ({targets['pct_tp3']:.1f}%)\n"
                f"🛑 SL: {f_sl} ({targets['pct_sl']:.1f}%)\n\n"
                f"• Trend: Price {'below' if bias == 'Bearish' else 'above'} 1H MA20 ({f_ma20})\n"
                f"• Momentum: RSI at {setup.rsi_1h:.1f}\n"
                f"Plan: Lock half at TP1, move stop to entry.\n\n"
                f"👇 Tap below to execute trade on {cashtag}!"
            ),
            # 4. Conversational Community Hook & Question
            "conversational": (
                f"guys, have you seen what’s happening with {cashtag} ? 🚨\n\n"
                f"Price made an aggressive push into {f_key_level}, but momentum is showing clear exhaustion on 1H/4H. "
                f"I'm not convinced {opponents} can hold this level.\n\n"
                f"Here’s what I’m watching right now 👇\n"
                f"Setup on {cashtag}:\n"
                f"📍 Entry: {f_entry_low} - {f_entry_high}\n"
                f"🛑 SL: {f_sl}\n"
                f"🎯 Targets: {f_tp1} ➔ {f_tp2} ➔ {f_tp3}\n\n"
                f"Are the {opponents} running out of fuel? 👇\n"
                f"Trade {cashtag} below! 🔥"
            ),
            # 5. Clean Snappy Trading Idea + Widget CTA
            "clean": (
                f"{cashtag} BIG {direction.upper()} : {base_asset} is testing key {level_type}, and a clean {'bounce' if direction == 'LONG' else 'rejection'} here "
                f"triggers another sharp move toward {'higher targets' if direction == 'LONG' else 'lower support'}!\n\n"
                f"Trading Setup {direction.upper()} {cashtag}:\n"
                f"📍 Entry: {f_entry_low} - {f_entry_high}\n"
                f"🛑 SL: {f_sl}\n"
                f"🎯 TP1: {f_tp1}\n"
                f"🎯 TP2: {f_tp2}\n"
                f"🎯 TP3: {f_tp3}\n\n"
                f"Trade {cashtag} here :👇"
            ),
            # 6. Whale / Order Book Trap Conviction
            "whale": (
                f"{cashtag} The harder they {'dump' if direction == 'LONG' else 'pump'} it into {level_type}, the harder the reversal! "
                f"That’s how big players trap late retail before the real trend expansion.\n\n"
                f"High Conviction {direction.upper()} Setup:\n"
                f"📍 Entry Zone: {f_entry_low} - {f_entry_high}\n"
                f"🎯 TP: {f_tp3}\n"
                f"🛑 SL: {f_sl} (R:R {setup.risk_reward:.1f})\n\n"
                f"Don't fight the smart money. Just go {direction.lower()} on {cashtag} and lock in gains! ⚡"
            ),
            # 7. Big Reversal / Flush Recovery Long/Short
            "reversal": (
                f"I’m going to open a BIG {direction.upper()} on {cashtag} here.\n\n"
                f"📍 Entry: {f_entry_low} - {f_entry_high}\n"
                f"🎯 TP: {f_tp3}\n"
                f"🛑 SL: {f_sl} 👇\n\n"
                f"Look at the chart: after that heavy move, {cashtag} is finally holding structure at {f_key_level} instead of {'breaking down' if direction == 'LONG' else 'breaking higher'}. "
                f"Risk-to-reward (1:{setup.risk_reward:.1f}) is prime and {opponents} are exhausted.\n\n"
                f"The {'flush' if direction == 'LONG' else 'pump'} already happened. Now let's catch the recovery wave!\n"
                f"Trade {cashtag} now! 🚀"
            ),
        }

        canonical_style = normalize_post_style(post_style)
        if canonical_style in templates_map:
            return templates_map[canonical_style]
        return random.choice(list(templates_map.values()))

    def generate_all_style_previews(self, coin: str = "BTCUSDT", direction: str = "LONG") -> Dict[str, str]:
        """Generates realistic post text previews for all supported post styles."""
        from src.technical_analysis import TradeSetup
        clean_coin = coin.replace("$", "").replace("/", "").strip().upper()
        if not clean_coin.endswith("USDT"):
            clean_coin += "USDT"

        is_long = direction.upper() == "LONG"
        price = 92450.0 if "BTC" in clean_coin else (3150.0 if "ETH" in clean_coin else 185.0)
        entry_low = round(price * 0.995, 2)
        entry_high = round(price * 1.005, 2)
        tp1 = round(price * 1.025, 2) if is_long else round(price * 0.975, 2)
        tp2 = round(price * 1.055, 2) if is_long else round(price * 0.945, 2)
        tp3 = round(price * 1.085, 2) if is_long else round(price * 0.915, 2)
        sl = round(price * 0.98, 2) if is_long else round(price * 1.02, 2)
        sup = round(price * 0.975, 2)
        res = round(price * 1.035, 2)

        sample_setup = TradeSetup(
            coin=clean_coin,
            direction="LONG" if is_long else "SHORT",
            current_price=price,
            entry_low=entry_low,
            entry_high=entry_high,
            target_price=tp3,
            stop_loss=sl,
            risk_reward=2.8,
            support_level=sup,
            resistance_level=res,
            rsi_1h=39.2 if is_long else 68.4,
            ma20_1h=round(price * 0.997, 2),
            ma50_1h=round(price * 0.991, 2),
            ma50_4h=round(price * 0.984, 2),
            timeframe="1h/4h",
            reasons=["Key structural liquidity sweep confirmed", "1H RSI momentum divergence"],
            df_1h=pd.DataFrame(),
            df_4h=pd.DataFrame(),
        )

        styles = ["sniper", "technical", "clean", "conversational", "danger_zone", "whale", "reversal"]
        previews = {}
        cashtag = f"${clean_coin.replace('USDT', '')}"
        bias = "Bullish" if is_long else "Bearish"
        for s in styles:
            previews[s] = self._generate_template_fallback(sample_setup, cashtag=cashtag, bias=bias, post_style=s)
        return previews
