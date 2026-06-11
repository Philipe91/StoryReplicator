import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ShieldCheck, AlertTriangle, TrendingUp, Eye, Zap } from "lucide-react";

export function VideoQualityCenter() {
  const alerts = [
    { title: "Pouca variedade visual", description: "Considere adicionar mais cenas B-Roll na metade do vídeo.", type: "warning" },
    { title: "Hook Forte", description: "A retenção nos primeiros 3 segundos está prevista para ser excelente.", type: "success" },
  ];

  return (
    <Card className="border-primary/20 shadow-lg">
      <CardHeader className="pb-3 bg-muted/20 border-b border-border/50">
        <CardTitle className="text-sm flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-primary" />
          Video Quality Center
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1"><TrendingUp className="w-3 h-3"/> Viral Score</span>
            <div className="text-xl font-bold text-emerald-500">89/100</div>
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1"><Eye className="w-3 h-3"/> CTR Previsto</span>
            <div className="text-xl font-bold text-blue-500">7.2%</div>
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1"><Zap className="w-3 h-3"/> Retenção</span>
            <div className="text-xl font-bold">65%</div>
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1"><ShieldCheck className="w-3 h-3"/> Áudio</span>
            <div className="text-xl font-bold">Ótimo</div>
          </div>
        </div>

        <div className="space-y-2 pt-2 border-t border-border/50">
          <span className="text-xs font-medium text-muted-foreground">Alertas Automáticos</span>
          {alerts.map((alert, i) => (
            <Alert key={i} variant={alert.type === "warning" ? "destructive" : "default"} className={`py-2 ${alert.type === "success" ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-500" : ""}`}>
              <div className="flex items-start gap-2">
                {alert.type === "warning" ? <AlertTriangle className="w-4 h-4 mt-0.5" /> : <ShieldCheck className="w-4 h-4 mt-0.5" />}
                <div>
                  <AlertTitle className="text-xs font-bold mb-0.5">{alert.title}</AlertTitle>
                  <AlertDescription className="text-[10px] opacity-90">
                    {alert.description}
                  </AlertDescription>
                </div>
              </div>
            </Alert>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
