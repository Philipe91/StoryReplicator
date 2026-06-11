import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BookOpen, Sparkles, MoveRight, Send } from "lucide-react";

export default function GeneratorPage() {
  const storyBlocks = [
    { label: "Hook (Gancho)", value: "90% das pessoas desistem quando estão prestes a vencer." },
    { label: "Contexto", value: "Você acorda todos os dias, vai para o trabalho, e sente que não sai do lugar." },
    { label: "Conflito", value: "A verdade é que seu cérebro está programado para buscar o conforto, não o sucesso." },
    { label: "Escalada", value: "E cada vez que você escolhe o caminho mais fácil, você afasta o seu sonho." },
    { label: "Twist (Reviravolta)", value: "Mas e se eu te dissesse que o desconforto é o único atalho verdadeiro?" },
    { label: "Final", value: "Comece a abraçar a dor hoje, e amanhã você não reconhecerá a si mesmo." },
    { label: "CTA", value: "Salve este vídeo para os dias em que quiser desistir." },
  ];

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto gap-6 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <BookOpen className="w-8 h-8 text-primary" />
            Story Generator
          </h1>
          <p className="text-muted-foreground mt-1">
            Editor visual da narrativa. Ajuste os blocos antes da geração final.
          </p>
        </div>
        <Button className="bg-primary hover:bg-primary/90 gap-2">
          <Sparkles className="w-4 h-4" />
          Refinar com IA
        </Button>
      </div>

      <div className="flex flex-col gap-4 relative">
        <div className="absolute left-6 top-8 bottom-8 w-px bg-border z-0"></div>
        {storyBlocks.map((block, i) => (
          <div key={i} className="flex gap-4 relative z-10">
            <div className="w-12 h-12 rounded-full bg-card border-2 border-border shadow-sm flex items-center justify-center font-bold text-muted-foreground shrink-0 mt-1">
              {i + 1}
            </div>
            <Card className="flex-1 hover:border-primary/50 transition-colors">
              <CardHeader className="py-3 bg-muted/20 border-b border-border/50">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {block.label}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <Input 
                  defaultValue={block.value} 
                  className="border-none bg-transparent shadow-none focus-visible:ring-0 px-0 font-medium text-lg" 
                />
              </CardContent>
            </Card>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-4 mt-4">
        <Button variant="outline" size="lg">Cancelar</Button>
        <Button size="lg" className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white">
          <Send className="w-4 h-4" />
          Aprovar Roteiro e Gerar Vídeo
        </Button>
      </div>
    </div>
  );
}
