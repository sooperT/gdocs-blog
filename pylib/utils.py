"""
Shared utility functions for blog generators
"""
from datetime import datetime


def format_date_for_display(iso_date):
    """
    Convert ISO date (YYYY-MM-DD) to display format (DD/MM/YYYY)
    """
    try:
        date_obj = datetime.strptime(iso_date, '%Y-%m-%d')
        return date_obj.strftime('%d/%m/%Y')
    except:
        return iso_date  # Return original if parsing fails
