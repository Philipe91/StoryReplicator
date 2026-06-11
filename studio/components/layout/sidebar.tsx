"use client";

import Link from "next/link";
import { LayoutDashboard, Compass, Clapperboard, Video, Settings, Activity, FolderOpen } from "lucide-react";
import { usePathname } from "next/navigation";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Viral Discovery", href: "/discovery", icon: Compass },
  { name: "Producer AI", href: "/producer", icon: Clapperboard },
  { name: "Human Director", href: "/editor", icon: Video },
  { name: "Assets", href: "/assets", icon: FolderOpen },
  { name: "Analytics", href: "/analytics", icon: Activity },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex flex-col w-64 bg-sidebar border-r border-sidebar-border h-full px-3 py-4">
      <div className="flex items-center gap-2 px-2 mb-8">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
          <Clapperboard className="w-5 h-5 text-primary-foreground" />
        </div>
        <span className="font-semibold text-lg text-sidebar-foreground">Studio V5</span>
      </div>
      
      <nav className="flex-1 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-2 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
              }`}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>
      
      <div className="mt-auto pt-4 border-t border-sidebar-border">
        <div className="px-2 py-2 text-sm text-muted-foreground">
          <div className="flex items-center justify-between mb-1">
            <span>Tokens</span>
            <span className="font-medium text-foreground">1,240</span>
          </div>
          <div className="w-full h-1.5 bg-sidebar-accent rounded-full overflow-hidden">
            <div className="h-full bg-primary w-2/3" />
          </div>
        </div>
      </div>
    </div>
  );
}
