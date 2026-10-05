import type { SVGProps } from "react";

import { cn } from "@/lib/utils";

type LogoProps = SVGProps<SVGSVGElement> & {
  variant?: "mark" | "full" | "accent";
};

export function Logo({ variant = "mark", className, ...props }: LogoProps) {
  if (variant === "full") {
    return (
      <svg
        viewBox="0 0 200 40"
        fill="none"
        className={cn("h-8 w-auto", className)}
        aria-label="ArtistAssist"
        {...props}
      >
        <path
          fill="currentColor"
          d="M4 34V6h5.25l7 18L23.25 6H28.5v28h-4.5V14.75L17.75 34h-4.25L7.25 14.75V34H4z"
        />
        <text
          x="40"
          y="27"
          fill="currentColor"
          fontFamily="Geist Sans, system-ui, sans-serif"
          fontSize="18"
          fontWeight="600"
          letterSpacing="-0.02em"
        >
          ArtistAssist
        </text>
      </svg>
    );
  }

  const fill = variant === "accent" ? "var(--color-vermilion)" : "currentColor";

  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={cn("size-8", className)}
      aria-hidden={variant === "mark"}
      aria-label={variant === "accent" ? "ArtistAssist" : undefined}
      {...props}
    >
      <path
        fill={fill}
        d="M8 26V6h4.2l5.6 14.4L23.4 6H28v20h-3.6V12.2L19.2 26h-3.4L10.6 12.2V26H8z"
      />
    </svg>
  );
}
