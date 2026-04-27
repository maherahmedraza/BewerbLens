"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRightOnRectangleIcon } from "@heroicons/react/24/outline";

import { createClient } from "@/lib/supabase/client";

interface SignOutButtonProps {
  children?: React.ReactNode;
  className?: string;
  onSignedOut?: () => void;
}

export default function SignOutButton({
  children = "Sign out",
  className,
  onSignedOut,
}: SignOutButtonProps) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    const supabase = createClient();
    setSigningOut(true);

    try {
      await supabase.auth.signOut();
      onSignedOut?.();
      router.push("/login");
      router.refresh();
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <button type="button" className={className} onClick={() => void handleSignOut()} disabled={signingOut}>
      <ArrowRightOnRectangleIcon width={18} height={18} />
      <span>{signingOut ? "Signing out..." : children}</span>
    </button>
  );
}
