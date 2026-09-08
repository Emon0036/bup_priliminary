"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Activity, BrainCircuit, Route, Users } from "lucide-react";

const fmt = (v: number) => new Intl.NumberFormat("en-BD", { style: "currency", currency: "BDT", maximumFractionDigits: 0 }).format(v);
export function Dashboard() {
  const [data, setData] = useState<any>(); const [error, setError] = useState("");
  useEffect(() => { api<any>("/api/dashboard").then(setData).catch(() => setError("The API is unavailable. Start the Python endpoint or deploy with Vercel.")); }, []);
  if (error) return <div className="card text-red-700">{error}</div>;
  if (!data) return <div className="card">Loading synthetic simulation...</div>;
  const m = data.metrics;
  const cards = [{ label: "Population", value: m.population, Icon: Users }, { label: "Employment rate", value: `${m.employment_rate}%`, Icon: Activity }, { label: "Average savings", value: fmt(m.average_savings), Icon: BrainCircuit }, { label: "Financial risk", value: `${m.at_risk_percentage}%`, Icon: Route }];
  return <div className="space-y-7"><section className="rounded-2xl bg-ink px-7 py-10 text-white"><p className="label text-teal-200">Artificial Intelligence Laboratory Project</p><h1 className="mt-2 text-4xl font-extrabold">Intelligent Economic Society Simulator</h1><p className="mt-3 max-w-2xl text-slate-200">Explore how economic shocks affect a virtual society powered by agent-based simulation and classical AI techniques.</p><div className="mt-6 flex gap-3"><Link className="button" href="/simulation">Run simulation</Link><Link className="button alt" href="/agents">Explore agents</Link></div></section><section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{cards.map(({ label, value, Icon }) => <div className="card" key={label}><div className="flex justify-between text-teal"><Icon /><span className="label">{label}</span></div><div className="metric">{value}</div></div>)}</section><section className="grid gap-4 lg:grid-cols-2"><div className="card"><p className="label">Current simulation</p><h2 className="mt-1 text-xl font-bold">Month {data.run.current_month} - 500 synthetic citizens</h2><p className="mt-3 text-sm text-slate-600">{data.events.length ? `${data.events.length} active/configured economic event(s).` : "No events injected yet. Establish a baseline or create an economic shock."}</p></div><div className="card"><p className="label">AI techniques</p><div className="mt-3 grid grid-cols-2 gap-2 text-sm"><span>A* Search</span><span>CSP allocation</span><span>Logistic Regression</span><span>Agent-based model</span></div></div></section></div>;
}
