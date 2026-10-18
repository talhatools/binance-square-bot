"""AI Writer: Uses Anthropic Claude API (or diverse competitor-style templates) to generate punchy, varied Binance Square posts."""
import random
import time
import logging
import re
from typing import Optional, Dict, Any, List
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
    ):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.disable_api = disable_api
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

    def generate_post_text(self, setup: TradeSetup) -> str:
        """
        Generates a Binance Square post dynamically styled after top-performing
        competitors (ranging from ultra-short sniper calls to detailed technical multi-TPs).
        """
        base_asset = setup.coin.replace("USDT", "")
        cashtag = f"${base_asset}"
        bias = "Bullish" if setup.direction == "LONG" else "Bearish"

        # If Claude API is disabled or not configured, generate a varied competitor template (free)
        if self.disable_api or not self.client or not self.api_key or self.api_key.startswith("your_"):
            logger.info("Using varied competitor-style template generator (free mode, no Claude API cost).")
            return self._generate_template_fallback(setup, cashtag, bias)

        prompt = self._build_prompt(setup, cashtag, bias)

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Calling Anthropic API ({self.model}) - Attempt {attempt + 1}")
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )

                response_text = message.content[0].text.strip()
                # Enforce no disclaimers, proper trade CTA, and character limit
                response_text = self._enforce_length_and_cta(response_text)

                logger.info(f"Generated AI post ({len(response_text)} chars):\n{response_text}")
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
        return self._generate_template_fallback(setup, cashtag, bias)

    def _build_prompt(self, setup: TradeSetup, cashtag: str, bias: str) -> str:
        base_asset = setup.coin.replace("USDT", "")
        action = "LONG" if setup.direction == "LONG" else "SHORT"
        targets = self._calculate_laddered_targets(setup)
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

    def _generate_template_fallback(self, setup: TradeSetup, cashtag: str, bias: str) -> str:
        """
        Deterministic varied template generator modeled directly on real high-performing
        competitor posts, varying dynamically between ultra-short, normal, and detailed setups.
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

        templates = [
            # 1. Ultra-Short / Fast Sniper Alert (Competitor 1 style)
            (
                f"🚀 Guys, {action} {cashtag} Now!\n\n"
                f"📍 Entry Current Price: {f_curr}\n\n"
                f"🎯 TP1: {f_tp1}\n"
                f"🎯 TP2: {f_tp2}\n\n"
                f"🛑 Stop Loss: {f_sl}\n\n"
                f"👉 Execute trade on {cashtag} now! 💰"
            ),

            # 2. Danger Zone / Liquidity Trap Breakdown (Competitor 2 style)
            (
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

            # 3. Technical Multi-Target Breakdown with % (Competitor 3 style)
            (
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

            # 4. Conversational Community Hook & Question (Competitor 4 & 7 style)
            (
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

            # 5. Clean Snappy Trading Idea + Widget CTA (Competitor 5 style)
            (
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

            # 6. Whale / Order Book Trap Conviction (Competitor 6 style)
            (
                f"{cashtag} The harder they {'dump' if direction == 'LONG' else 'pump'} it into {level_type}, the harder the reversal! "
                f"That’s how big players trap late retail before the real trend expansion.\n\n"
                f"High Conviction {direction.upper()} Setup:\n"
                f"📍 Entry Zone: {f_entry_low} - {f_entry_high}\n"
                f"🎯 TP: {f_tp3}\n"
                f"🛑 SL: {f_sl} (R:R {setup.risk_reward:.1f})\n\n"
                f"Don't fight the smart money. Just go {direction.lower()} on {cashtag} and lock in gains! ⚡"
            ),

            # 7. Big Reversal / Flush Recovery Long/Short (Competitor 9 style)
            (
                f"I’m going to open a BIG {direction.upper()} on {cashtag} here.\n\n"
                f"📍 Entry: {f_entry_low} - {f_entry_high}\n"
                f"🎯 TP: {f_tp3}\n"
                f"🛑 SL: {f_sl} 👇\n\n"
                f"Look at the chart: after that heavy move, {cashtag} is finally holding structure at {f_key_level} instead of {'breaking down' if direction == 'LONG' else 'breaking higher'}. "
                f"Risk-to-reward (1:{setup.risk_reward:.1f}) is prime and {opponents} are exhausted.\n\n"
                f"The {'flush' if direction == 'LONG' else 'pump'} already happened. Now let's catch the recovery wave!\n"
                f"Trade {cashtag} now! 🚀"
            ),
        ]
        return random.choice(templates)
