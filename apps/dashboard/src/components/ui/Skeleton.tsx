import styles from "./Skeleton.module.css";

interface Props {
  className?: string;
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
}

export default function Skeleton({ className = "", width, height, borderRadius }: Props) {
  return (
    <div 
      className={`${styles.skeleton} ${className}`} 
      style={{ 
        width: typeof width === "number" ? `${width}px` : width,
        height: typeof height === "number" ? `${height}px` : height,
        borderRadius: typeof borderRadius === "number" ? `${borderRadius}px` : borderRadius,
      }} 
    />
  );
}
