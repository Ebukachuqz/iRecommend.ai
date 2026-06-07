"use client";

import { motion } from "framer-motion";
import { Sparkles, Star, Users } from "lucide-react";

const metrics = [
  {
    label: "847 reviews analysed",
    icon: Sparkles,
    className: "text-primary",
  },
  {
    label: "12 personas built",
    icon: Users,
    className: "text-success",
  },
  {
    label: "4.1/5 avg prediction",
    icon: Star,
    className: "text-warning",
  },
];

export function HeroMetrics() {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: {
          transition: {
            delayChildren: 0.6,
            staggerChildren: 0.12,
          },
        },
      }}
      className="mt-12 grid w-full gap-3 sm:grid-cols-3"
    >
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <motion.div
            key={metric.label}
            variants={{
              hidden: { opacity: 0, y: 18 },
              visible: { opacity: 1, y: 0 },
            }}
            transition={{ duration: 0.45, ease: "easeOut" }}
            className="violet-glow-card rounded-lg px-4 py-3"
          >
            <div className="flex items-center justify-center gap-2 text-sm font-semibold">
              <Icon className={`h-4 w-4 ${metric.className}`} />
              <span className={metric.className}>{metric.label}</span>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
