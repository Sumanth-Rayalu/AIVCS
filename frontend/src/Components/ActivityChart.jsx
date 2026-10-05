import { ChevronDown } from "lucide-react";
import { PanelHeading } from "./PanelHeading";

export function ActivityChart() {
  return (
    <section className="mt-4 overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
      <PanelHeading
        title="Contribution activity"
        subtitle="Your coding activity over the last year"
        action={
          <button className="inline-flex items-center gap-[7px] rounded-[5px] border border-[#30363d] bg-[#1c232b] px-[9px] py-[7px] text-[10px] text-[#8b949e]">
            Last 12 months <ChevronDown size={14} />
          </button>
        }
      />
      <div className="flex h-[195px] px-5 pb-[18px] max-sm:px-2.5">
        <div className="flex w-[30px] flex-col justify-between py-1 pb-[22px] text-[9px] text-[#6e7681] max-sm:w-[23px]">
          <span>40</span>
          <span>30</span>
          <span>20</span>
          <span>10</span>
          <span>0</span>
        </div>
        <div className="relative flex-1">
          <div className="absolute inset-x-0 top-0 bottom-[22px] bg-[repeating-linear-gradient(to_bottom,rgba(139,148,158,0.12)_0,rgba(139,148,158,0.12)_1px,transparent_1px,transparent_25%)]" />
          <svg
            className="relative h-[calc(100%-22px)] w-full"
            viewBox="0 0 800 155"
            preserveAspectRatio="none"
          >
            <path
              d="M0 135 C40 132 55 110 90 118 S145 98 178 108 S220 77 260 88 S310 80 342 100 S388 55 428 76 S475 65 512 82 S560 45 600 65 S650 60 688 72 S740 25 800 40"
              fill="none"
              stroke="#8b78f6"
              strokeWidth="2.5"
            />
            <path
              d="M0 135 C40 132 55 110 90 118 S145 98 178 108 S220 77 260 88 S310 80 342 100 S388 55 428 76 S475 65 512 82 S560 45 600 65 S650 60 688 72 S740 25 800 40 V155 H0Z"
              fill="url(#fade)"
              opacity=".35"
            />
            <defs>
              <linearGradient id="fade" x1="0" x2="0" y1="0" y2="1">
                <stop stopColor="#8173e8" />
                <stop offset="1" stopColor="#8173e8" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
          <div className="flex justify-between text-[9px] text-[#6e7681]">
            <span>Oct</span>
            <span>Dec</span>
            <span>Feb</span>
            <span>Apr</span>
            <span>Jun</span>
            <span>Aug</span>
            <span>Sep</span>
          </div>
        </div>
      </div>
    </section>
  );
}
