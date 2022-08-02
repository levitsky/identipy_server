from django.template import Library

register = Library()

@register.filter
def index(sequence, position):
    return sequence[position]

register.filter(index)
