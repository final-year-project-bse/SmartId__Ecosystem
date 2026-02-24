"""
Notification list, mark-read, and mark-all-read (UC-5).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notification


@login_required
def list_notifications(request):
    """List notifications for current user."""
    unread = Notification.objects.filter(user=request.user, read=False).count()
    notifications = Notification.objects.filter(user=request.user)[:50]
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'unread': unread,
    })


@login_required
def mark_read(request, pk):
    """Mark a single notification as read."""
    if request.method != 'POST':
        return redirect('notifications:list')
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.read = True
    n.save(update_fields=['read'])
    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    """Mark all notifications as read."""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        messages.success(request, 'All notifications marked as read.')
    return redirect('notifications:list')
