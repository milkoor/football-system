"""数据库模型定义"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime

from config.database import Base


class LeagueIndex(Base):
    """联赛索引表"""
    __tablename__ = "league_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    country = Column(String(100), nullable=False)
    league_id = Column(Integer, nullable=False)
    league_name_zh = Column(String(200), nullable=False)
    league_name_tw = Column(String(200), nullable=False)
    display_order = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    seasons = relationship("Season", back_populates="league")
    matches = relationship("Match", back_populates="league")


class Season(Base):
    """赛季表"""
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    league_id = Column(Integer, ForeignKey("league_index.id"), nullable=False)
    season_label = Column(String(50), nullable=False)
    season_start = Column(Date)
    season_end = Column(Date)
    status = Column(String(20), default="active")  # active, completed, archived
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    league = relationship("LeagueIndex", back_populates="seasons")
    matches = relationship("Match", back_populates="season_rel")


class Match(Base):
    """比赛日程表"""
    __tablename__ = "matches"

    match_id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("league_index.id"))
    season_id = Column(Integer, ForeignKey("seasons.id"))
    league_name = Column(String(200))
    season = Column(String(50))
    group_name = Column(String(100))
    round_name = Column(String(100))
    match_time = Column(DateTime)
    home_team = Column(String(200))
    away_team = Column(String(200))
    score_ft = Column(String(20))
    score_ht = Column(String(20))
    # 结算相关字段
    settlement = Column(String(50))  # 结算结果文字: 主赢, 客赢半, 等
    settlement_value = Column(Float, default=0.0)  # 结算值: 1.0=全赢/全输, 0.5=半赢/半输
    settlement_direction = Column(String(20))  # win/lose
    home_away_direction = Column(String(20))  # home/away
    target_team = Column(String(200))  # 结算目标队伍
    crawl_status = Column(String(20), default="pending")  # pending, completed, error, failed, nodata, live
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    last_synced = Column(DateTime, default=datetime.utcnow)

    # 关系
    league = relationship("LeagueIndex", back_populates="matches")
    season_rel = relationship("Season", back_populates="matches")
    odds_movements = relationship("OddsMovement", back_populates="match")
    x_values = relationship("XValueResult", back_populates="match")


class OddsMovement(Base):
    """赔率变动表"""
    __tablename__ = "odds_movements"

    movement_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.match_id"), nullable=False)
    odds_type = Column(String(10), nullable=False)  # AH, OU, 1x2
    is_half_time = Column(Boolean, default=False)
    elapsed_time = Column(String(20))
    score_at_time = Column(String(20))
    update_time = Column(DateTime)
    status = Column(String(20))  # 早(Early), 即(Live), 走(In-Play)
    home_rate = Column(Float)
    handicap_raw = Column(String(50))
    handicap_std = Column(Float)
    away_rate = Column(Float)

    # 关系
    match = relationship("Match", back_populates="odds_movements")


class XValueResult(Base):
    """X值计算结果表（系统 B 需要读取）"""
    __tablename__ = "x_value_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.match_id"), nullable=False)
    home_team = Column(String(200))
    away_team = Column(String(200))
    score = Column(String(20))
    target_team = Column(String(200))
    has_star_mark = Column(Boolean)
    x_value = Column(Float)
    status = Column(String(20))  # success, not_suitable, no_data
    calculation_note = Column(Text)
    movement_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    match = relationship("Match", back_populates="x_values")


class CrawlJob(Base):
    """爬虫任务记录表"""
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), unique=True, nullable=False)
    league_id = Column(Integer)
    season_label = Column(String(50))
    match_ids = Column(Text)  # JSON 格式存储比赛 ID 列表
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    total_matches = Column(Integer, default=0)
    completed_matches = Column(Integer, default=0)
    failed_matches = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)