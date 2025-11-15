"""
Quest XP calculation utilities
Calculates XP based on D&D 5e CR to XP table from DMG
"""

# Official D&D 5e CR to XP conversion table (DMG p.275, MM p.9)
CR_TO_XP = {
    "0": 0,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}


def cr_to_xp(cr: str) -> int:
    """
    Convert CR string to XP value using official D&D 5e table

    Args:
        cr: Challenge Rating as string (e.g., "1", "1/2", "5")

    Returns:
        XP value for that CR

    Raises:
        ValueError: If CR is invalid
    """
    if cr not in CR_TO_XP:
        raise ValueError(f"Invalid CR: {cr}")
    return CR_TO_XP[cr]


def calculate_quest_xp(monsters: list) -> dict:
    """
    Calculate total XP from a list of monsters

    Args:
        monsters: List of dicts with 'cr' and 'count' keys
                 e.g., [{'cr': '5', 'count': 2, 'monster_name': 'Dragon'}]

    Returns:
        Dict with:
            - total_xp: Total XP from all monsters
            - breakdown: List of dicts with monster details and XP
            - monster_count: Total number of monsters
    """
    total_xp = 0
    breakdown = []
    monster_count = 0

    for monster in monsters:
        cr = monster.get('cr')
        count = monster.get('count', 1)
        monster_name = monster.get('monster_name')

        try:
            xp_per_monster = cr_to_xp(cr)
            monster_total_xp = xp_per_monster * count
            total_xp += monster_total_xp
            monster_count += count

            breakdown.append({
                'cr': cr,
                'count': count,
                'monster_name': monster_name,
                'xp_per_monster': xp_per_monster,
                'total_xp': monster_total_xp
            })
        except ValueError as e:
            # Skip invalid CR values
            breakdown.append({
                'cr': cr,
                'count': count,
                'monster_name': monster_name,
                'error': str(e)
            })

    return {
        'total_xp': total_xp,
        'breakdown': breakdown,
        'monster_count': monster_count
    }


def calculate_xp_per_participant(total_xp: int, participant_count: int) -> int:
    """
    Calculate XP per participant (evenly distributed)

    Args:
        total_xp: Total XP to distribute
        participant_count: Number of participants

    Returns:
        XP per participant (rounded down)
    """
    if participant_count == 0:
        return 0
    return total_xp // participant_count


def format_quest_xp_summary(quest_xp_data: dict, participants: list) -> str:
    """
    Format a readable summary of quest XP calculation

    Args:
        quest_xp_data: Result from calculate_quest_xp()
        participants: List of participant dicts with 'character_name' and 'starting_level'

    Returns:
        Formatted string summary
    """
    summary = []

    # Monster breakdown
    summary.append("**Monsters Defeated:**")
    for monster in quest_xp_data['breakdown']:
        if 'error' in monster:
            name_part = f"{monster['monster_name']} - " if monster['monster_name'] else ""
            summary.append(f"  ❌ {monster['count']}x {name_part}CR {monster['cr']} - {monster['error']}")
        else:
            name_part = f"{monster['monster_name']} - " if monster['monster_name'] else ""
            summary.append(
                f"  • {monster['count']}x {name_part}CR {monster['cr']} "
                f"({monster['xp_per_monster']:,} XP each = {monster['total_xp']:,} XP)"
            )

    summary.append(f"\n**Total XP:** {quest_xp_data['total_xp']:,}")
    summary.append(f"**Total Monsters:** {quest_xp_data['monster_count']}")

    # Per participant
    if participants:
        participant_count = len(participants)
        xp_per_participant = calculate_xp_per_participant(
            quest_xp_data['total_xp'],
            participant_count
        )

        summary.append(f"\n**Participants:** {participant_count}")
        summary.append(f"**XP per Participant:** {xp_per_participant:,}")

        summary.append("\n**Participant Details:**")
        for p in participants:
            summary.append(f"  • {p['character_name']} (Level {p['starting_level']})")

    return "\n".join(summary)
