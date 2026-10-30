'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Vacío = mismo origen (Vercel rewrite /api/* -> index.py). En local: NEXT_PUBLIC_API_URL=http://localhost:8000
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

interface Interval { lower: number; upper: number }
interface CoefficientStats { estimate: number; std_error: number; confidence_interval: Interval }
interface LinearityResult {
  slope: number;
  intercept: number;
  r_squared: number;
  is_compliant: boolean;
  verdict: 'PASS' | 'FAIL';
  n_points: number;
  confidence_level: number;
  slope_stats: CoefficientStats;
  intercept_stats: CoefficientStats;
  audit: { request_id: string; timestamp_utc: string; engine_version: string; input_sha256: string };
}

const NUMERIC = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

// Convierte "10, 20; 30" en números; rechaza cualquier token no numérico (nunca descarta en silencio).
function parseNumberList(raw: string, label: string): number[] {
  const tokens = raw.split(/[,;\s]+/).filter(t => t.length > 0);
  return tokens.map((t) => {
    if (!NUMERIC.test(t)) throw new Error(`${label}: valor no numérico "${t}".`);
    return Number(t);
  });
}

export default function Home() {
  const [concentrations, setConcentrations] = useState('10.0, 20.0, 30.0, 40.0, 50.0');
  const [areas, setAreas] = useState('12520.0, 24985.0, 37540.0, 50012.0, 62490.0');
  const [result, setResult] = useState<LinearityResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRunningAnalysis, setIsRunningAnalysis] = useState(false);
  const [importMessage, setImportMessage] = useState('');

  // Manejador de importación CSV
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const lines = text.replace(/^﻿/, '').split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);
        if (lines.length === 0) throw new Error('El archivo está vacío.');

        // Delimitador: ';' > tab > ','  (con ';' o tab se acepta coma decimal)
        const delim = lines[0].includes(';') ? ';' : lines[0].includes('\t') ? '\t' : ',';
        const num = (s: string) => {
          let t = s.trim();
          if (delim !== ',' && (t.match(/,/g) ?? []).length === 1 && !t.includes('.')) t = t.replace(',', '.');
          return NUMERIC.test(t) ? t : null;
        };

        const concs: string[] = [];
        const arqs: string[] = [];
        const problems: string[] = [];

        lines.forEach((line, idx) => {
          const parts = line.split(delim);
          const c = parts.length >= 2 ? num(parts[0]) : null;
          const a = parts.length >= 2 ? num(parts[1]) : null;
          if (idx === 0 && parts.length >= 2 && c === null && a === null) return; // encabezado
          if (c === null || a === null) {
            problems.push(`Línea ${idx + 1}: fila no válida.`);
            return;
          }
          concs.push(c);
          arqs.push(a);
        });

        if (problems.length > 0) {
          // Nunca se descartan filas en silencio: se aborta la importación.
          setImportMessage(`Error: importación abortada. ${problems.slice(0, 5).join(' ')}${problems.length > 5 ? ` (+${problems.length - 5} más)` : ''}`);
        } else if (concs.length > 0) {
          setConcentrations(concs.join(', '));
          setAreas(arqs.join(', '));
          setResult(null);
          setError('');
          setImportMessage(`Importado: ${concs.length} puntos desde ${file.name}`);
        } else {
          setImportMessage('Error: no se encontraron filas numéricas.');
        }
      } catch (err) {
        setImportMessage(err instanceof Error ? `Error: ${err.message}` : 'Error al procesar el archivo CSV.');
      }
    };
    reader.readAsText(file);
  };

  const handleCalculate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setIsRunningAnalysis(true);
    setError('');
    setResult(null);

    try {
      const body = {
        concentrations: parseNumberList(concentrations, 'Concentraciones'),
        areas: parseNumberList(areas, 'Áreas'),
        r_squared_limit: 0.999,
      };
      const res = await fetch(`${API_BASE}/api/v1/linearity/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const details: string[] = data?.error?.details ?? [];
        throw new Error([data?.error?.message ?? `Error del servidor (${res.status}).`, ...details].join(' '));
      }
      setResult(data as LinearityResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo contactar al motor de cálculo.');
    } finally {
      setLoading(false);
      setIsRunningAnalysis(false);
    }
  };

  // Función para exportar los resultados analíticos
  const handleExportReport = () => {
    if (!result) return;
    const ci = (s: CoefficientStats) => `[${s.confidence_interval.lower.toFixed(4)}, ${s.confidence_interval.upper.toFixed(4)}]`;
    const reportContent = `--- KRITERION HPLC VALIDATION REPORT ---\n` +
      `Fecha del cálculo (UTC): ${result.audit.timestamp_utc}\n` +
      `ID de solicitud: ${result.audit.request_id}\n` +
      `Versión del motor: ${result.audit.engine_version}\n` +
      `SHA-256 de entradas: ${result.audit.input_sha256}\n` +
      `Referencia: ICH Q2(R2)\n` +
      `Concentraciones: ${concentrations}\n` +
      `Áreas de Pico: ${areas}\n` +
      `n: ${result.n_points}\n` +
      `Pendiente: ${result.slope} IC${(result.confidence_level * 100).toFixed(0)}% ${ci(result.slope_stats)}\n` +
      `Intercepto: ${result.intercept} IC${(result.confidence_level * 100).toFixed(0)}% ${ci(result.intercept_stats)}\n` +
      `R²: ${result.r_squared}\n` +
      `Dictamen: ${result.verdict === 'PASS' ? 'APROBADO (PASS)' : 'NO APROBADO (FAIL)'}\n`;

    const blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Kriterion_Validation_Report_${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="min-h-screen bg-[#FBFBFD] text-slate-900 selection:bg-slate-900 selection:text-white relative overflow-hidden font-sans">
      
      {/* Gradiente ambiental puro */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1100px] h-[550px] bg-gradient-to-b from-slate-200/50 to-transparent rounded-full blur-3xl pointer-events-none" />

      {/* Barra de Navegación Clean Apple */}
      <nav className="border-b border-slate-200/80 bg-white/70 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-slate-900 flex items-center justify-center shadow-md shadow-slate-900/10">
              <span className="text-white text-base font-semibold">⚗️</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-tight text-slate-900">Kriterion</h1>
              <p className="text-[10px] text-slate-500 font-mono tracking-wider uppercase">HPLC Validation Engine</p>
            </div>
          </div>
          
          {/* Bandas de Normas en la Barra */}
          <div className="hidden md:flex items-center space-x-2">
            {['ICH Q2(R2)', 'ALCOA+', '21 CFR Part 11', 'USP <1225>'].map((norm, idx) => (
              <span key={idx} className="px-2.5 py-1 rounded-full text-[11px] font-mono bg-slate-100 text-slate-600 border border-slate-200/80">
                {norm}
              </span>
            ))}
          </div>
        </div>
      </nav>

      {/* Contenido Principal */}
      <div className="max-w-7xl mx-auto px-6 py-16 relative z-10">
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 20 }}
          className="text-center max-w-3xl mx-auto space-y-4 mb-16"
        >
          <span className="inline-block px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-medium border border-slate-200 tracking-wide">
            Arquitectura Analítica de Confianza Cero
          </span>
          <h2 className="text-4xl lg:text-6xl font-semibold tracking-tight text-slate-900 leading-[1.1]">
            Pureza matemática para la <span className="text-transparent bg-clip-text bg-gradient-to-r from-slate-800 via-slate-600 to-indigo-900">industria farmacéutica</span>.
          </h2>
          <p className="text-slate-500 text-lg font-light leading-relaxed">
            Un motor determinista por Mínimos Cuadrados Ordinarios (OLS) diseñado para automatizar validaciones cromatográficas con fluidez de grado industrial.
          </p>
        </motion.div>

        {/* Grid Principal */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Columna Izquierda: Entrada y CSV */}
          <motion.div 
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 25 }}
            className="lg:col-span-6 bg-white/80 border border-slate-200/80 rounded-3xl p-8 backdrop-blur-xl shadow-xl shadow-slate-200/50 relative"
          >
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold text-slate-900">Parámetros de Linealidad</h3>
                <p className="text-sm text-slate-500">Cargue un archivo CSV o ingrese los valores tabulares.</p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-dashed border-slate-300 text-center relative hover:border-slate-400 transition cursor-pointer">
                <input 
                  type="file" 
                  accept=".csv, .txt" 
                  onChange={handleFileUpload}
                  className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                />
                <div className="space-y-1">
                  <p className="text-xs font-medium text-slate-700">📂 Importar reporte de cromatógrafo (CSV)</p>
                  <p className="text-[11px] text-slate-400">Arrastre su archivo o haga clic para explorar</p>
                </div>
              </div>

              {importMessage && (
                <p className="text-xs font-mono text-emerald-600 bg-emerald-50 p-2.5 rounded-xl border border-emerald-200">
                  {importMessage}
                </p>
              )}

              <form onSubmit={handleCalculate} className="space-y-5">
                <div>
                  <label className="block text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
                    Concentraciones (µg/mL)
                  </label>
                  <input 
                    type="text" 
                    value={concentrations}
                    onChange={(e) => setConcentrations(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
                    Áreas de Pico (Peak Areas)
                  </label>
                  <input 
                    type="text" 
                    value={areas}
                    onChange={(e) => setAreas(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition font-mono"
                  />
                </div>

                <button 
                  type="submit"
                  disabled={loading}
                  className="w-full py-4 rounded-2xl bg-slate-900 text-white font-medium shadow-lg shadow-slate-900/15 hover:bg-slate-800 transition-all duration-300 flex items-center justify-center space-x-2 text-sm"
                >
                  {loading ? (
                    <span className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  ) : (
                    <span>Calcular linealidad (OLS) ➔</span>
                  )}
                </button>
              </form>

              {error && (
                <p className="text-xs font-mono text-red-700 bg-red-50 p-2.5 rounded-xl border border-red-200">
                  {error}
                </p>
              )}

              {/* Panel de Resultados con Animación de Spring */}
              <AnimatePresence>
                {result && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95, y: 15 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ type: "spring", stiffness: 300, damping: 25 }}
                    className="mt-6 p-6 rounded-2xl bg-slate-50 border border-slate-200/60 space-y-4 font-mono text-sm"
                  >
                    <div className="flex justify-between items-center border-b border-slate-200/60 pb-3">
                      <span className="text-slate-500">Coeficiente (R²):</span>
                      <span className="text-slate-900 font-bold text-base">{result.r_squared.toFixed(7)}</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-slate-200/60 pb-3">
                      <span className="text-slate-500">Pendiente (β₁):</span>
                      <span className="text-slate-800 font-semibold">{result.slope.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-slate-200/60 pb-3">
                      <span className="text-slate-500">Intercepto (β₀):</span>
                      <span className="text-slate-800 font-semibold">{result.intercept.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between items-center pt-1">
                      <span className="text-slate-500">Dictamen ICH Q2(R2):</span>
                      {result.verdict === 'PASS' ? (
                        <span className="px-3 py-1 rounded-full text-xs bg-emerald-100 text-emerald-800 font-medium border border-emerald-200">
                          APROBADO (PASS)
                        </span>
                      ) : (
                        <span className="px-3 py-1 rounded-full text-xs bg-red-100 text-red-800 font-medium border border-red-200">
                          NO APROBADO (FAIL)
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 break-all pt-1">
                      SHA-256 entradas: {result.audit.input_sha256}
                    </p>

                    {/* Botón de Exportación */}
                    <button 
                      onClick={handleExportReport}
                      className="w-full mt-2 py-3 rounded-xl bg-white border border-slate-300 text-slate-800 font-medium hover:bg-slate-100 transition shadow-sm flex items-center justify-center space-x-2 text-xs"
                    >
                      <span>📥 Exportar Reporte de Validación (TXT/CSV)</span>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>

          {/* Columna Derecha: Animación Fluida Tubería HPLC y Cromatograma */}
          <motion.div 
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 25 }}
            className="lg:col-span-6 bg-gradient-to-br from-white via-slate-50 to-slate-100 border border-slate-200/80 rounded-3xl p-8 shadow-xl shadow-slate-200/40 flex flex-col justify-between space-y-6"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-widest">Simulación en Tiempo Real</span>
                <span className="text-xs font-medium text-slate-600 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                  {isRunningAnalysis ? "Inyectando muestra..." : "Sistema Estable"}
                </span>
              </div>
              <h4 className="text-2xl font-semibold text-slate-900 tracking-tight">Tubería Capilar & Detector UV</h4>
              <p className="text-sm text-slate-500 mt-1">
                Visualización fluida del tránsito de analitos a través del capilar de sílice hacia la celda de flujo.
              </p>
            </div>

            {/* Animación Tubería HPLC */}
            <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm relative overflow-hidden h-28 flex items-center">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#f1f5f9_1px,transparent_1px)] bg-[size:1.5rem_1.5rem]" />
              
              <div className="relative w-full h-1.5 bg-slate-100 rounded-full flex items-center">
                {/* Partícula fluida con física de resorte */}
                {isRunningAnalysis && (
                  <motion.div 
                    initial={{ x: "-10%", scale: 0.8 }}
                    animate={{ x: "105%", scale: 1.2 }}
                    transition={{ duration: 1.1, ease: [0.25, 1, 0.5, 1] }}
                    className="absolute w-5 h-5 bg-slate-900 rounded-full shadow-lg flex items-center justify-center"
                  >
                    <div className="w-2.5 h-2.5 bg-indigo-400 rounded-full animate-ping" />
                  </motion.div>
                )}

                <div className="absolute right-1/4 -top-3 transform -translate-x-1/2 flex flex-col items-center">
                  <span className="text-[9px] font-mono text-slate-400 mb-1">UV Cell</span>
                  <div className="w-5 h-7 rounded bg-slate-900 border border-slate-700 shadow-sm flex items-center justify-center">
                    <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                  </div>
                </div>
              </div>
            </div>

            {/* Cromatograma Dinámico Fluido */}
            <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm relative overflow-hidden flex items-end h-40">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#f1f5f9_1px,transparent_1px),linear-gradient(to_bottom,#f1f5f9_1px,transparent_1px)] bg-[size:2rem_2rem]" />
              
              <svg className="absolute inset-0 w-full h-full text-slate-800 p-4" preserveAspectRatio="none" viewBox="0 0 500 150">
                <motion.path 
                  d="M 0,150 Q 50,150 70,120 T 100,20 T 130,120 Q 160,150 200,150 T 280,145 Q 310,140 330,80 T 360,140 Q 400,150 500,150" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2.5"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1.4, ease: "easeInOut" }}
                />
              </svg>
              
              <div className="relative z-10 flex justify-between w-full text-[10px] font-mono text-slate-400 border-t border-slate-100 pt-2">
                <span>0.0 min</span>
                <span>Retención (tR)</span>
                <span>10.0 min</span>
              </div>
            </div>

            {/* Bandas de Cumplimiento Inferiores */}
            <div className="grid grid-cols-3 gap-3 pt-2 border-t border-slate-200/60">
              <div className="bg-white p-3 rounded-2xl border border-slate-200/60 shadow-sm text-center">
                <p className="text-sm font-bold text-slate-900 font-mono">ALCOA+</p>
                <p className="text-[10px] text-slate-500">Trazabilidad</p>
              </div>
              <div className="bg-white p-3 rounded-2xl border border-slate-200/60 shadow-sm text-center">
                <p className="text-sm font-bold text-slate-900 font-mono">21 CFR P11</p>
                <p className="text-[10px] text-slate-500">Auditable</p>
              </div>
              <div className="bg-white p-3 rounded-2xl border border-slate-200/60 shadow-sm text-center">
                <p className="text-sm font-bold text-slate-900 font-mono">SHA-256</p>
                <p className="text-[10px] text-slate-500">Huella de entradas</p>
              </div>
            </div>

          </motion.div>

        </div>

      </div>

    </main>
  );
}