import { useState, useEffect } from 'react';
import { Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/api/client';

export default function NotificationBell() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    api.get('/notifications/unread-count').then(r => setCount(r.data.count)).catch(() => {});
    const interval = setInterval(() => {
      api.get('/notifications/unread-count').then(r => setCount(r.data.count)).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Button variant="ghost" size="sm" className="relative" data-testid="notification-bell">
      <Bell size={16} />
      {count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
          {count > 9 ? '9+' : count}
        </span>
      )}
    </Button>
  );
}
