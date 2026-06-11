"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { CheckCircle2, CircleDashed, Loader2, PlayCircle, Server } from "lucide-react";
import { Button } from "@/components/ui/button";

// Esse componente simula o que será conectado ao WebSocket do FastAPI
export function JobProgressOverlay() {
  const [logs, setLogs] = useState<string[]>([
    "[14:01:22] Iniciando processo de geração...",
    "[14:01:25] Extraindo dados do vídeo base...",
    "[14:01:48] Executive Producer AI: Gerando hooks e DNA viral...",
  ]);
  const [progress, setProgress] = useState(35);
  const [isOpen, setIsOpen] = useState(true);

  if (!isOpen) return (
    <Button 
      variant="outline" 
      size="sm" 
      className="fixed bottom-4 right-4 shadow-xl border-primary/50 text-primary bg-background/80 backdrop-blur-md"
      onClick={() => setIsOpen(true)}
    >
      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
      Gerando Vídeo (35%)
    </Button>
  );

  return (
    <div className="fixed bottom-4 right-4 w-[400px] z-50 animate-in slide-in-from-bottom-5">
      <Card className="shadow-2xl border-primary/20 bg-background/95 backdrop-blur-md">
        <CardHeader className="py-3 border-b border-border flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Server className="w-4 h-4 text-primary" />
            Live Generation
          </CardTitle>
          <Button variant="ghost" size="icon" className="w-6 h-6 -mr-2 text-muted-foreground" onClick={() => setIsOpen(false)}>
            <span className="sr-only">Minimizar</span>
            &minus;
          </Button>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Progresso</span>
              <span>ETA: 2m 14s</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span className="text-muted-foreground">Extração & Análise</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
              <span className="font-medium text-foreground">Story Generator & Assets</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <CircleDashed className="w-4 h-4 text-muted-foreground/50" />
              <span className="text-muted-foreground/50">Renderização (Remotion)</span>
            </div>
          </div>

          <div className="bg-black/50 border border-border rounded-md p-3 h-32 overflow-y-auto font-mono text-[10px] text-muted-foreground space-y-1">
            {logs.map((log, i) => (
              <div key={i} className={i === logs.length - 1 ? "text-primary/90" : ""}>{log}</div>
            ))}
          </div>
          
          <Button className="w-full h-8 text-xs" variant="destructive">Cancelar Geração</Button>
        </CardContent>
      </Card>
    </div>
  );
}
