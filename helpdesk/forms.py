from django import forms

from .models import Ticket, TicketReply


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "description", "category"]


class TicketReplyForm(forms.ModelForm):
    class Meta:
        model = TicketReply
        fields = ["message"]
