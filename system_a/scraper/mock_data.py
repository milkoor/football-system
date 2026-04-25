"""模拟数据模块

用于在爬虫无法访问目标网站时提供测试数据
"""

MOCK_LEAGUES = [
    {
        "league_id": 36,
        "name": "英超",
        "country": "英格兰"
    },
    {
        "league_id": 31,
        "name": "意甲",
        "country": "意大利"
    },
    {
        "league_id": 8,
        "name": "西甲",
        "country": "西班牙"
    },
    {
        "league_id": 11,
        "name": "德甲",
        "country": "德国"
    },
    {
        "league_id": 16,
        "name": "法甲",
        "country": "法国"
    },
    {
        "league_id": 34,
        "name": "荷甲",
        "country": "荷兰"
    },
    {
        "league_id": 23,
        "name": "葡超",
        "country": "葡萄牙"
    },
    {
        "league_id": 18,
        "name": "俄超",
        "country": "俄罗斯"
    },
    {
        "league_id": 17,
        "name": "土超",
        "country": "土耳其"
    },
    {
        "league_id": 30,
        "name": "苏超",
        "country": "苏格兰"
    },
    {
        "league_id": 7,
        "name": "比甲",
        "country": "比利时"
    },
    {
        "league_id": 26,
        "name": "奥甲",
        "country": "奥地利"
    },
    {
        "league_id": 24,
        "name": "丹超",
        "country": "丹麦"
    },
    {
        "league_id": 29,
        "name": "瑞士超",
        "country": "瑞士"
    },
    {
        "league_id": 14,
        "name": "日职联",
        "country": "日本"
    },
    {
        "league_id": 15,
        "name": "韩K联",
        "country": "韩国"
    },
    {
        "league_id": 4,
        "name": "中超",
        "country": "中国"
    },
    {
        "league_id": 6,
        "name": "亚冠杯",
        "country": "亚洲"
    },
    {
        "league_id": 2,
        "name": "欧冠杯",
        "country": "欧洲"
    },
    {
        "league_id": 3,
        "name": "欧罗巴",
        "country": "欧洲"
    },
    {
        "league_id": 5,
        "name": "世界杯",
        "country": "国际"
    },
    {
        "league_id": 9,
        "name": "欧洲杯",
        "country": "欧洲"
    },
    {
        "league_id": 10,
        "name": "美洲杯",
        "country": "美洲"
    },
    {
        "league_id": 12,
        "name": "非洲杯",
        "country": "非洲"
    }
]

MOCK_MATCHES = {
    36: [  # 英超
        {
            "match_id": 123456,
            "league_id": 36,
            "league_name": "英超",
            "season": "2024-2025",
            "round_name": "第38轮",
            "match_time_str": "2025-05-19 22:00",
            "home_team": "曼城",
            "away_team": "阿森纳",
            "score_ft": "2-1"
        },
        {
            "match_id": 123457,
            "league_id": 36,
            "league_name": "英超",
            "season": "2024-2025",
            "round_name": "第38轮",
            "match_time_str": "2025-05-19 22:00",
            "home_team": "利物浦",
            "away_team": "切尔西",
            "score_ft": "3-0"
        }
    ],
    31: [  # 意甲
        {
            "match_id": 223456,
            "league_id": 31,
            "league_name": "意甲",
            "season": "2024-2025",
            "round_name": "第38轮",
            "match_time_str": "2025-05-20 00:30",
            "home_team": "尤文图斯",
            "away_team": "AC米兰",
            "score_ft": "1-1"
        }
    ]
}
