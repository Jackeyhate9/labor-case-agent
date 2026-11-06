"use client";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const saved = localStorage.getItem("theme") === "dark";
    setDark(saved);
    document.documentElement.classList.toggle("dark", saved);
  }, []);
  function toggle() {
    const n = !dark;
    setDark(n);
    document.documentElement.classList.toggle("dark", n);
    localStorage.setItem("theme", n ? "dark" : "light");
  }
  return (
    <button
      className="icon-button"
      onClick={toggle}
      aria-label={dark ? "切换到亮色" : "切换到暗色"}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
