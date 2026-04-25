"""Raw_Data_Reader：從前處理後的 Excel 賠率數據檔案讀取比賽紀錄。

支援解析 Row 1 metadata 進行交叉驗證，並從 Row 2+ 提取 MatchRecord 列表。
"""

import logging
from pathlib import Path

import pandas as pd

from etl.models import MatchRecord

logger = logging.getLogger(__name__)


class RawDataReader:
    """原始數據讀取器：讀取 RPA 產出的 xlsx 檔案並提取比賽紀錄。"""

    def read(self, filepath: str) -> pd.DataFrame:
        """使用 openpyxl 讀取 xlsx 檔案為 DataFrame。

        Args:
            filepath: xlsx 檔案路徑。

        Returns:
            讀取到的 DataFrame（header=None），錯誤時回傳空 DataFrame。
        """
        path = Path(filepath)
        if not path.exists():
            logger.error("檔案不存在：%s", filepath)
            return pd.DataFrame()

        try:
            df = pd.read_excel(filepath, engine="openpyxl", header=None)
        except Exception as exc:
            logger.error("讀取 xlsx 檔案失敗 (%s)：%s", filepath, exc)
            return pd.DataFrame()

        if df.empty:
            logger.warning("檔案內容為空：%s", filepath)
            return pd.DataFrame()

        return df

    def extract_metadata(self, df: pd.DataFrame) -> dict | None:
        """提取 Row 1 metadata 並進行基本驗證。

        Row 1 格式：A1=國家、B1=聯賽名、C1=賽季、D1=玩法。

        Args:
            df: 由 read() 回傳的 DataFrame。

        Returns:
            包含 country、league_name、season、play_type 的 dict，
            metadata 缺失或無效時回傳 None。
        """
        if df.empty or len(df) < 1:
            logger.warning("DataFrame 為空，無法提取 metadata")
            return None

        if len(df.columns) < 4:
            logger.warning("DataFrame 欄位不足 4 欄，無法提取 metadata")
            return None

        row = df.iloc[0]
        country = row.iloc[0]
        league_name = row.iloc[1]
        season = row.iloc[2]
        play_type = row.iloc[3]

        # 檢查是否有 NaN 或空值
        values = [country, league_name, season, play_type]
        if any(pd.isna(v) for v in values):
            logger.warning("metadata 含有空值：%s", values)
            return None

        # 轉為字串
        metadata = {
            "country": str(country).strip(),
            "league_name": str(league_name).strip(),
            "season": str(season).strip(),
            "play_type": str(play_type).strip(),
        }

        # 檢查是否有空字串
        if any(v == "" for v in metadata.values()):
            logger.warning("metadata 含有空字串：%s", metadata)
            return None

        return metadata

    def extract_records(self, df: pd.DataFrame) -> list[MatchRecord]:
        """從清理後的 DataFrame 提取 MatchRecord 列表。

        跳過 Row 1（metadata），從 Row 2（index 1）開始處理。
        欄位對應：A欄=輪次、B欄=主隊、D欄=客隊、E欄=X值、F欄=結算。

        Args:
            df: 由 read() 回傳並經前處理的 DataFrame。

        Returns:
            MatchRecord 列表，跳過無效資料列。
        """
        if df.empty:
            logger.warning("DataFrame 為空，無法提取紀錄")
            return []

        if len(df) < 2:
            logger.warning("DataFrame 只有 metadata 列，無比賽資料")
            return []

        if len(df.columns) < 6:
            logger.warning("DataFrame 欄位不足 6 欄（需要 A~F），無法提取紀錄")
            return []

        records: list[MatchRecord] = []
        skipped = 0

        # 從 index 1 開始（跳過 Row 1 metadata）
        for idx in range(1, len(df)):
            row = df.iloc[idx]

            # 提取原始值
            raw_round = row.iloc[0]
            raw_home = row.iloc[1]
            raw_away = row.iloc[3]
            raw_x = row.iloc[4]
            raw_settlement = row.iloc[5]

            # 驗證輪次：必須是有效數字
            try:
                round_num = int(float(raw_round))
            except (ValueError, TypeError):
                logger.warning("第 %d 列輪次無效（值=%s），跳過", idx + 1, raw_round)
                skipped += 1
                continue

            # 驗證主隊與客隊：不可為空
            if pd.isna(raw_home) or str(raw_home).strip() == "":
                logger.warning("第 %d 列主隊為空，跳過", idx + 1)
                skipped += 1
                continue

            if pd.isna(raw_away) or str(raw_away).strip() == "":
                logger.warning("第 %d 列客隊為空，跳過", idx + 1)
                skipped += 1
                continue

            # 驗證 X 值：必須是有效浮點數
            try:
                x_value = float(raw_x)
            except (ValueError, TypeError):
                logger.warning("第 %d 列 X 值無效（值=%s），跳過", idx + 1, raw_x)
                skipped += 1
                continue

            # 結算欄位：允許為空（某些情況下尚未結算）
            if pd.isna(raw_settlement):
                settlement = ""
            else:
                settlement = str(raw_settlement).strip()

            record = MatchRecord(
                round_num=round_num,
                home_team=str(raw_home).strip(),
                away_team=str(raw_away).strip(),
                x_value=x_value,
                settlement=settlement,
            )
            records.append(record)

        if skipped > 0:
            logger.info("共跳過 %d 列無效資料", skipped)

        logger.info("成功提取 %d 筆比賽紀錄", len(records))
        return records

    def read_from_postgresql(
        self,
        league_id: int = None,
        season_label: str = None,
        match_ids: list = None
    ) -> dict:
        """從系統A PostgreSQL讀取數據並提取MatchRecord列表。

        從 x_value_results 和 matches 表聯合查詢。

        Args:
            league_id: 過濾指定聯賽的比賽
            season_id: 過濾指定賽季的比賽
            match_ids: 過濾指定比賽ID列表

        Returns:
            MatchRecord 列表，跳過無效資料列。
        """
        from etl.models import MatchRecord

        result_data = {
            'leagues': [],
            'seasons': [],
            'matches_by_league_season': {}
        }

        try:
            # 獲取數據庫連接配置
            from config.settings import get_settings
            from sqlalchemy import create_engine, text
            from sqlalchemy.orm import sessionmaker

            settings = get_settings()
            engine = create_engine(settings.system_a_database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            # 第一步: 獲取聯賽信息
            league_query = """
                SELECT id, country, league_name_tw, league_name_zh
                FROM league_index
                WHERE enabled = TRUE
            """
            league_params = {}
            if league_id:
                league_query += " AND id = :league_id"
                league_params['league_id'] = league_id

            league_result = session.execute(text(league_query), league_params)
            league_rows = league_result.fetchall()

            league_map = {}
            for row in league_rows:
                league_id_val = row[0]
                country = row[1] or ''
                league_name_tw = row[2] or ''
                league_name_zh = row[3] or ''
                name_zh = league_name_tw or league_name_zh
                if not name_zh:
                    continue

                league_info = {
                    'id': league_id_val,
                    'name_zh': name_zh,
                    'country': country
                }
                result_data['leagues'].append(league_info)
                league_map[league_id_val] = league_info

            # 第二步: 獲取賽季信息
            season_query = """
                SELECT id, league_id, season_label
                FROM seasons
                WHERE 1=1
            """
            season_params = {}
            if league_id:
                season_query += " AND league_id = :league_id"
                season_params['league_id'] = league_id
            if season_label:
                season_query += " AND season_label = :season_label"
                season_params['season_label'] = season_label

            season_result = session.execute(text(season_query), season_params)
            season_rows = season_result.fetchall()

            season_map = {}
            for row in season_rows:
                season_id_val = row[0]
                league_id_val = row[1]
                season_label_val = row[2]

                season_info = {
                    'id': season_id_val,
                    'league_id': league_id_val,
                    'label': season_label_val,
                    'season': season_label_val
                }
                result_data['seasons'].append(season_info)
                season_map[(league_id_val, season_label_val)] = season_info

            # 第三步: 獲取比賽數據和X值結果
            match_query = """
                SELECT
                    m.match_id,
                    m.league_id,
                    m.season,
                    m.round_name,
                    m.home_team,
                    m.away_team,
                    m.score_ft,
                    xv.x_value,
                    xv.target_team,
                    xv.has_star_mark,
                    xv.calculation_note,
                    m.settlement
                FROM matches m
                INNER JOIN x_value_results xv ON m.match_id = xv.match_id
                WHERE xv.x_value IS NOT NULL
            """
            match_params = {}

            if league_id:
                match_query += " AND m.league_id = :league_id"
                match_params['league_id'] = league_id

            if season_label:
                match_query += " AND m.season = :season_label"
                match_params['season_label'] = season_label

            if match_ids:
                match_query += " AND m.match_id IN :match_ids"
                match_params['match_ids'] = tuple(match_ids)

            match_query += " ORDER BY m.match_time"

            # 執行查詢
            match_result = session.execute(text(match_query), match_params)
            match_rows = match_result.fetchall()

            for row in match_rows:
                match_id = row[0]
                league_id_val = row[1]
                season_val = row[2]
                round_name = row[3]
                home_team = row[4]
                away_team = row[5]
                score_ft = row[6]
                x_value = row[7]
                target_team = row[8]
                has_star_mark = row[9]
                calculation_note = row[10]
                settlement = row[11]

                if x_value is None:
                    logger.warning(f"比賽 {match_id} 缺少X值，跳過")
                    continue

                # 解析輪次
                round_num = 1
                try:
                    if round_name and round_name.strip():
                        # 嘗試解析輪次號碼
                        if round_name.startswith('R_'):
                            round_num = int(round_name[2:])
                        else:
                            try:
                                round_num = int(round_name)
                            except ValueError:
                                round_num = 1
                except Exception:
                    logger.warning(f"比賽 {match_id} 輪次無效: {round_name}")
                    round_num = 1

                # 創建MatchRecord
                record = MatchRecord(
                    round_num=round_num,
                    home_team=home_team if home_team else '',
                    away_team=away_team if away_team else '',
                    x_value=x_value,
                    settlement=settlement if settlement else '',
                    score=score_ft if score_ft else '',
                    target_team=target_team if target_team else '',
                    match_id=str(match_id),
                    is_completed=bool(settlement)
                )

                # 組織數據 - 預設歸為 HDP/Early
                key = (league_id_val, season_val)
                if key not in result_data['matches_by_league_season']:
                    result_data['matches_by_league_season'][key] = {
                        'HDP': {
                            'Early': [],
                            'RT': []
                        },
                        'OU': {
                            'Early': [],
                            'RT': []
                        }
                    }

                # 暫時都添加到 HDP/Early
                result_data['matches_by_league_season'][key]['HDP']['Early'].append(record)

            total_records = sum(
                len(records)
                for season_data in result_data['matches_by_league_season'].values()
                for play_type_data in season_data.values()
                for records in play_type_data.values()
            )
            logger.info(f"從PostgreSQL成功讀取 {total_records} 筆比賽記錄")
            session.close()

        except Exception as exc:
            logger.error(f"從PostgreSQL讀取數據失敗: {exc}")
            import traceback
            logger.error(traceback.format_exc())

        return result_data
