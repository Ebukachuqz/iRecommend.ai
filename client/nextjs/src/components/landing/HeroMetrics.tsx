"use client";

import { motion } from "framer-motion";

const nodes = [
  { cx: 82, cy: 54, r: 7 },
  { cx: 142, cy: 30, r: 6 },
  { cx: 198, cy: 70, r: 8 },
  { cx: 136, cy: 106, r: 11 },
  { cx: 72, cy: 132, r: 6 },
  { cx: 218, cy: 132, r: 6 },
];

const lines = [
  [82, 54, 142, 30],
  [142, 30, 198, 70],
  [198, 70, 136, 106],
  [136, 106, 82, 54],
  [136, 106, 72, 132],
  [136, 106, 218, 132],
];

export function HeroMetrics() {
  return (
    <motion.svg
      viewBox="0 0 288 176"
      role="img"
      aria-label="Abstract customer persona intelligence network"
      className="mx-auto mt-12 h-40 w-full max-w-sm"
      initial="hidden"
      animate="visible"
    >
      <motion.g
        variants={{
          hidden: {},
          visible: { transition: { delayChildren: 0.25, staggerChildren: 0.08 } },
        }}
      >
        {lines.map(([x1, y1, x2, y2], index) => (
          <motion.line
            key={`${x1}-${y1}-${x2}-${y2}`}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#DDD6FE"
            strokeWidth="2"
            strokeLinecap="round"
            variants={{
              hidden: { pathLength: 0, opacity: 0 },
              visible: { pathLength: 1, opacity: 1 },
            }}
            transition={{ duration: 0.45, ease: "easeOut", delay: 0.25 + index * 0.04 }}
          />
        ))}
        {nodes.map((node, index) => (
          <motion.circle
            key={`${node.cx}-${node.cy}`}
            cx={node.cx}
            cy={node.cy}
            r={node.r}
            fill={index === 3 ? "#5B21B6" : "#DDD6FE"}
            stroke="#5B21B6"
            strokeWidth={index === 3 ? "2" : "1.5"}
            variants={{
              hidden: { opacity: 0, scale: 0.7 },
              visible: { opacity: 1, scale: 1 },
            }}
            transition={{ duration: 0.28, ease: "easeOut" }}
          />
        ))}
      </motion.g>
    </motion.svg>
  );
}
