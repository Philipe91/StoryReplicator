import { VideoPreview } from "@/components/modules/video-player";
import { VideoQualityCenter } from "@/components/modules/video-quality-center";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SlidersHorizontal, Image as ImageIcon, Music, Type } from "lucide-react";

export default function EditorPage() {
  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Human Director Studio</h1>
          <p className="text-sm text-muted-foreground">Projeto: Viral Motivacional #49</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">Salvar Draft</Button>
          <Button className="bg-primary hover:bg-primary/90">Renderizar Final</Button>
        </div>
      </div>

      <div className="flex gap-4 h-[55vh]">
        {/* Preview Area */}
        <div className="flex-1 rounded-xl bg-card border border-border shadow-sm flex items-center justify-center p-4">
          <VideoPreview />
        </div>

        {/* Inspector Area */}
        <Card className="w-80 flex flex-col">
          <CardHeader className="py-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4" />
              Inspector - Cena 1
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">Prompt Original</label>
              <div className="text-sm bg-muted/50 p-2 rounded-md border border-border">
                "Você sabia que 90% das pessoas desistem antes..."
              </div>
            </div>
            
            <div className="space-y-2 pt-2">
              <label className="text-xs font-medium text-muted-foreground">Visual Asset</label>
              <div className="aspect-video bg-muted rounded-md flex flex-col items-center justify-center border border-border cursor-pointer hover:border-primary transition-colors">
                <ImageIcon className="w-6 h-6 text-muted-foreground mb-1" />
                <span className="text-xs text-muted-foreground">Substituir Imagem</span>
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-medium text-muted-foreground">Movimento Câmera</label>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" size="sm" className="text-xs">Zoom In</Button>
                <Button variant="outline" size="sm" className="text-xs">Pan Dir</Button>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Quality Center Area */}
        <div className="w-80 overflow-y-auto">
          <VideoQualityCenter />
        </div>
      </div>

      {/* Timeline Area */}
      <Card className="flex-1 overflow-hidden flex flex-col">
        <CardHeader className="py-3 border-b border-border bg-muted/20">
          <CardTitle className="text-sm flex items-center gap-4">
            Timeline
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="w-6 h-6"><ImageIcon className="w-3 h-3" /></Button>
              <Button variant="ghost" size="icon" className="w-6 h-6"><Music className="w-3 h-3" /></Button>
              <Button variant="ghost" size="icon" className="w-6 h-6"><Type className="w-3 h-3" /></Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-0 bg-muted/10 relative overflow-x-auto">
          {/* Tracks Mock */}
          <div className="min-w-[800px] h-full flex flex-col gap-1 p-2">
            <div className="flex items-center h-12 bg-background border border-border rounded-md px-2 gap-2">
              <div className="w-16 text-xs text-muted-foreground font-medium border-r border-border h-full flex items-center">Visual</div>
              <div className="flex-1 h-8 bg-blue-500/20 border border-blue-500/50 rounded flex items-center px-2 text-xs text-blue-400">Cena 1 (4.2s)</div>
              <div className="flex-1 h-8 bg-muted border border-border rounded flex items-center px-2 text-xs text-muted-foreground">Cena 2 (3.1s)</div>
            </div>
            <div className="flex items-center h-12 bg-background border border-border rounded-md px-2 gap-2">
              <div className="w-16 text-xs text-muted-foreground font-medium border-r border-border h-full flex items-center">Áudio</div>
              <div className="w-3/4 h-8 bg-emerald-500/20 border border-emerald-500/50 rounded flex items-center px-2 text-xs text-emerald-400">Narração Completa (TTS)</div>
            </div>
            <div className="flex items-center h-12 bg-background border border-border rounded-md px-2 gap-2">
              <div className="w-16 text-xs text-muted-foreground font-medium border-r border-border h-full flex items-center">Música</div>
              <div className="w-full h-8 bg-purple-500/20 border border-purple-500/50 rounded flex items-center px-2 text-xs text-purple-400">Suspense Loop - Hindenburg</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
