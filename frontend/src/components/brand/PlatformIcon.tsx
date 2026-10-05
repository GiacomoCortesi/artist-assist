import { BookOpen } from "lucide-react";
import {
  siDeezer,
  siFacebook,
  siInstagram,
  siSoundcloud,
  siSpotify,
  siThreads,
  siTiktok,
  siYoutube,
  type SimpleIcon,
} from "simple-icons";

import { cn } from "@/lib/utils";

const PLATFORM_ICONS: Record<string, SimpleIcon> = {
  deezer: siDeezer,
  facebook: siFacebook,
  instagram: siInstagram,
  soundcloud: siSoundcloud,
  spotify: siSpotify,
  threads: siThreads,
  tiktok: siTiktok,
  youtube: siYoutube,
};

export function platformDisplayName(source: string): string {
  const icon = PLATFORM_ICONS[source];
  if (icon) return icon.title;
  return source.charAt(0).toUpperCase() + source.slice(1);
}

export function PlatformIcon({
  source,
  className,
}: {
  source: string;
  className?: string;
}) {
  const icon = PLATFORM_ICONS[source];
  if (!icon) {
    return <BookOpen className={cn("size-3.5 shrink-0", className)} aria-hidden />;
  }
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("size-3.5 shrink-0 fill-current", className)}
      aria-hidden
    >
      <title>{icon.title}</title>
      <path d={icon.path} />
    </svg>
  );
}
