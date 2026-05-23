"""Avatars endpoint — quản lý 50 avatar VN preset + custom upload."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


# 50 avatar VN preset — production: load từ DB
AVATAR_PRESETS = [
    {
        "id": "vn_female_hanoi_22yo_casual",
        "name": "Cô gái Hà Nội 22 tuổi - Casual",
        "ethnicity": "Northern Vietnamese",
        "age": 22,
        "gender": "female",
        "style": "Hanoi casual streetwear, oversized t-shirt, jeans",
        "vibe": "friendly approachable",
        "image_url": "https://r2.com/avatars/vn_female_hanoi_22yo_casual.png",
        "is_preset": True,
    },
    {
        "id": "vn_female_hanoi_28yo_pro",
        "name": "Chị Hà Nội 28 tuổi - Văn phòng",
        "ethnicity": "Northern Vietnamese",
        "age": 28,
        "gender": "female",
        "style": "Hanoi office casual, blazer + jeans",
        "vibe": "professional confident",
        "image_url": "https://r2.com/avatars/vn_female_hanoi_28yo_pro.png",
        "is_preset": True,
    },
    {
        "id": "vn_female_saigon_25yo_aesthetic",
        "name": "Cô gái Sài Gòn 25 - Aesthetic",
        "ethnicity": "Southern Vietnamese",
        "age": 25,
        "gender": "female",
        "style": "Saigon minimalist aesthetic, beige tone outfit",
        "vibe": "aesthetic minimalist",
        "image_url": "https://r2.com/avatars/vn_female_saigon_25yo_aesthetic.png",
        "is_preset": True,
    },
    {
        "id": "vn_female_saigon_30yo_mom",
        "name": "Mẹ bỉm sữa SG 30 tuổi",
        "ethnicity": "Southern Vietnamese",
        "age": 30,
        "gender": "female",
        "style": "casual lifestyle mom",
        "vibe": "warm caring",
        "image_url": "https://r2.com/avatars/vn_female_saigon_30yo_mom.png",
        "is_preset": True,
    },
    {
        "id": "vn_male_hanoi_28yo_freelance",
        "name": "Anh Hà Nội 28 - Freelance",
        "ethnicity": "Northern Vietnamese",
        "age": 28,
        "gender": "male",
        "style": "Hanoi cafe freelancer, white tee + denim jacket",
        "vibe": "chill creative",
        "image_url": "https://r2.com/avatars/vn_male_hanoi_28yo_freelance.png",
        "is_preset": True,
    },
    # ... 45 more avatars (production seed)
]


@router.get("/")
async def list_avatars(
    ethnicity: str = None,
    gender: str = None,
    age_min: int = None,
    age_max: int = None,
):
    """List avatar presets với filter."""
    results = AVATAR_PRESETS.copy()

    if ethnicity:
        results = [a for a in results if a["ethnicity"] == ethnicity]

    if gender:
        results = [a for a in results if a["gender"] == gender]

    if age_min:
        results = [a for a in results if a["age"] >= age_min]

    if age_max:
        results = [a for a in results if a["age"] <= age_max]

    return {"avatars": results, "total": len(results)}


@router.get("/{avatar_id}")
async def get_avatar(avatar_id: str):
    """Get 1 avatar by ID."""
    for avatar in AVATAR_PRESETS:
        if avatar["id"] == avatar_id:
            return avatar
    raise HTTPException(status_code=404, detail=f"Avatar {avatar_id} không tồn tại")
