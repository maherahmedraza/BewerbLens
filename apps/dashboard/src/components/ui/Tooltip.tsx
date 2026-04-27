"use client";

import { ReactNode, useState, useRef, useEffect, useId } from "react";
import { InformationCircleIcon } from "@heroicons/react/24/outline";
import styles from "./Tooltip.module.css";

interface TooltipProps {
  content: ReactNode;
  children?: ReactNode;
  iconOnly?: boolean;
}

export default function Tooltip({ content, children, iconOnly = false }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const tooltipId = useId();

  // Close on click outside for mobile touch support
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (tooltipRef.current && !tooltipRef.current.contains(event.target as Node)) {
        setIsVisible(false);
      }
    }
    
    if (isVisible) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isVisible]);

  return (
    <div 
      className={styles.tooltipContainer} 
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onClick={() => setIsVisible(!isVisible)}
      ref={tooltipRef}
      role="button"
      tabIndex={0}
      aria-describedby={isVisible ? tooltipId : undefined}
      aria-expanded={isVisible}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setIsVisible((current) => !current);
        }
        if (event.key === "Escape") {
          setIsVisible(false);
        }
      }}
    >
      {iconOnly ? (
        <InformationCircleIcon className={styles.icon} />
      ) : (
        children
      )}
      
      {isVisible && (
        <div id={tooltipId} role="tooltip" className={styles.tooltipBox}>
          {content}
        </div>
      )}
    </div>
  );
}
