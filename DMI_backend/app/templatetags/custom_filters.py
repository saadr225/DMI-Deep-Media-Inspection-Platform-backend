from django import template

register = template.Library()

@register.filter
def map_action_types(action_list, action_type):
    """
    Filter moderator actions by action type
    Usage: {{ moderator_actions|map_action_types:'approve' }}
    """
    return [action for action in action_list if action.action_type == action_type] 