"""X value calculation module

Calculate X value from System A odds data

X value rules:
1. Only use "early" (早) and "live" (即) status odds (exclude "rolling" 滚)
2. Check if initial handicap has red * mark:
   - Has * mark: calculate away team odds
   - No * mark: calculate home team odds
3. Calculation: X = sum of handicap segment changes
   - Take earliest record's handicap
   - Find this handicap's last occurrence (from both ends)
   - Calculate x = last_occurrence_rate - earliest_rate
   - Then continue from after the last occurrence
   - X = x1 + x2 + x3 + ...
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class XValueCalculator:
    """X value calculator"""

    FLAT_HANDICAP_VALUE = 0.0
    FLAT_HANDICAP_NAMES = {"平手", "平手盘", "0"}

    def __init__(self, data_connector=None):
        self.data_connector = data_connector

    def calculate_from_match(
        self,
        match_id: int,
        odds_type: str = "AH",
    ) -> Dict[str, Any]:
        """Calculate X value from odds data"""
        if not self.data_connector:
            from modules.data_connector import get_connector
            self.data_connector = get_connector()

        try:
            movements = self.data_connector.get_match_odds(
                match_id=match_id,
                odds_type=odds_type,
            )
        except Exception as e:
            logger.error(f"Failed to get odds data: {e}")
            return {
                "match_id": match_id,
                "status": "error",
                "calculation_note": f"Failed to get data: {e}",
                "x_value": None,
            }

        if not movements:
            return {
                "match_id": match_id,
                "status": "no_data",
                "calculation_note": "No odds data",
                "x_value": None,
            }

        return self._calculate_x_value(match_id, movements)

    def _calculate_x_value(
        self,
        match_id: int,
        movements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate X value"""
        # Filter early and live data (exclude rolling)
        # 兼容多种状态格式：中文（早、即）、英文（Early、Live）、时间格式等
        filtered = []
        for m in movements:
            status = m.get("status", "")
            # 如果状态是"早"或"即"，直接使用
            if status in ["早", "即", "Early", "Live"]:
                filtered.append(m)
            # 如果状态是时间格式（如"4-21 22:03"），假设都是"早"
            elif status and (":" in status or "-" in status):
                filtered.append(m)
            # 如果状态为空，也假设是"早"
            elif not status:
                filtered.append(m)

        if not filtered:
            return {
                "match_id": match_id,
                "status": "no_data",
                "calculation_note": "No early or live odds data",
                "x_value": None,
            }

        # Check initial handicap for * mark
        first_handicap = filtered[-1].get("handicap_raw", "")
        has_star_mark = "*" in first_handicap or "受" in first_handicap

        # Check if initial handicap is flat (平手)
        if first_handicap == "平手":
            return {
                "match_id": match_id,
                "status": "not_suitable",
                "calculation_note": "Initial handicap is flat, X not applicable",
                "x_value": None,
            }

        # Calculate by squeeze logic
        x_value, note = self._calculate_by_squeeze(filtered, has_star_mark)

        return {
            "match_id": match_id,
            "home_team": filtered[-1].get("home_team"),
            "away_team": filtered[-1].get("away_team"),
            "score": filtered[-1].get("score_at_time"),
            "target_team": "away" if has_star_mark else "home",
            "has_star_mark": has_star_mark,
            "x_value": x_value,
            "status": "success",
            "calculation_note": note,
            "movement_url": f"https://vip.titan007.com/changeDetail/handicap.aspx?id={match_id}&companyID=3",
        }

    def _calculate_by_squeeze(
        self,
        movements: List[Dict],
        has_star_mark: bool,
    ) -> Tuple[Optional[float], str]:
        """Calculate X value by squeeze method

        Logic (user clarified):
        1. Take earliest record's handicap as target
        2. Skip the very first record (initial value)
        3. Find this handicap's last occurrence
        4. Calculate x = last_occurrence_rate - earliest_rate
        5. Then continue from after the last occurrence
        6. X = x1 + x2 + x3 + ...
        """
        if not movements:
            return None, "No valid data"

        # Data is in reverse time order (newest first), reverse to get chronological order
        chron = list(reversed(movements))

        # Skip the very first record (initial value)
        if len(chron) > 1:
            chron = chron[1:]

        # Choose rate field: away for * mark, home otherwise
        rate_key = "away_rate" if has_star_mark else "home_rate"

        changes = []
        total_x = 0.0
        i = 0

        while i < len(chron):
            # Take current record's handicap as target
            target_handicap = chron[i].get("handicap_raw", "")
            if not target_handicap:
                i += 1
                continue

            earliest = chron[i]
            earliest_rate = earliest.get(rate_key)

            # Find this handicap's last occurrence (squeeze from both ends)
            # Search from the end to find the last occurrence of this handicap
            last_idx = i
            for j in range(len(chron) - 1, i - 1, -1):
                if chron[j].get("handicap_raw") == target_handicap:
                    last_idx = j
                    break

            latest = chron[last_idx]
            latest_rate = latest.get(rate_key)

            if earliest_rate is not None and latest_rate is not None:
                change = round(latest_rate - earliest_rate, 3)
                changes.append({
                    "handicap": target_handicap,
                    "earliest_rate": earliest_rate,
                    "latest_rate": latest_rate,
                    "change": change,
                })
                total_x += change

            # Move to after the last occurrence
            i = last_idx + 1

        if not changes:
            return None, "Cannot calculate odds change"

        x_value = round(total_x, 3)

        # Build explanation
        change_strs = [f"{c['handicap']}: {c['latest_rate']} - {c['earliest_rate']} = {c['change']}" for c in changes]
        note = f"Handicap changed, sum changes: {' + '.join(change_strs)} = {x_value}"

        logger.info(f"X value calculation: X={x_value}, {note}")

        return x_value, note

    def calculate_from_raw_data(
        self,
        raw_odds_list: List[Dict[str, Any]],
        has_star_mark: bool = False,
    ) -> Dict[str, Any]:
        """Calculate X value directly from raw odds data (for testing)"""
        if not raw_odds_list:
            return {
                "status": "no_data",
                "x_value": None,
            }

        filtered = [m for m in raw_odds_list if m.get("status") in ["早", "即"]]

        if not filtered:
            return {
                "status": "no_data",
                "calculation_note": "No early or live status data",
                "x_value": None,
            }

        first_handicap = filtered[-1].get("handicap_raw", "")
        if first_handicap == "平手":
            return {
                "status": "not_suitable",
                "calculation_note": "Initial handicap is flat",
                "x_value": None,
            }

        x_value, note = self._calculate_by_squeeze(filtered, has_star_mark)

        return {
            "x_value": x_value,
            "status": "success" if x_value is not None else "not_suitable",
            "calculation_note": note,
            "has_star_mark": has_star_mark,
        }

    def batch_calculate(
        self,
        match_ids: List[int],
        odds_type: str = "AH",
    ) -> List[Dict[str, Any]]:
        """Batch calculate X values"""
        results = []
        for match_id in match_ids:
            try:
                result = self.calculate_from_match(match_id, odds_type)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to calculate X value for match_id={match_id}: {e}")
                results.append({
                    "match_id": match_id,
                    "status": "error",
                    "calculation_note": str(e),
                    "x_value": None,
                })

        return results


if __name__ == "__main__":
    pass