import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BrainCircuit, Target, TrendingUp, Globe, FileText, Anchor, Type, Image as ImageIcon, Dna, Share2, ClipboardList } from "lucide-react";

export default function ProducerPage() {
  return (
    <div className="flex flex-col h-full gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <BrainCircuit className="w-8 h-8 text-primary" />
          Executive Producer AI
        </h1>
        <p className="text-muted-foreground mt-1">
          Análise profunda de nicho e roteirização viral guiada por dados.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card className="col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Target className="w-4 h-4" />
              Alvo e Nicho
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold">Motivação & Mindset</div>
            <p className="text-sm text-muted-foreground">Subnicho: Superação Pessoal</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-500" />
              Viral Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-500">92/100</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Share2 className="w-4 h-4 text-blue-500" />
              Replication
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-500">Alta</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Globe className="w-4 h-4 text-purple-500" />
              International
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-500">88/100</div>
          </CardContent>
        </Card>
      </div>

      <Card className="flex-1 overflow-hidden flex flex-col shadow-xl border-border/50">
        <Tabs defaultValue="hooks" className="flex-1 flex flex-col h-full">
          <div className="px-6 pt-4 pb-2 border-b border-border bg-muted/10">
            <TabsList className="bg-muted/50 border border-border">
              <TabsTrigger value="analysis" className="gap-2"><FileText className="w-4 h-4" /> Análise</TabsTrigger>
              <TabsTrigger value="hooks" className="gap-2"><Anchor className="w-4 h-4" /> Hooks Lab</TabsTrigger>
              <TabsTrigger value="titles" className="gap-2"><Type className="w-4 h-4" /> Titles Lab</TabsTrigger>
              <TabsTrigger value="thumbnails" className="gap-2"><ImageIcon className="w-4 h-4" /> Thumbnails Lab</TabsTrigger>
              <TabsTrigger value="dna" className="gap-2"><Dna className="w-4 h-4" /> Viral DNA</TabsTrigger>
              <TabsTrigger value="cross" className="gap-2"><Share2 className="w-4 h-4" /> Cross Niche</TabsTrigger>
              <TabsTrigger value="notes" className="gap-2"><ClipboardList className="w-4 h-4" /> Producer Notes</TabsTrigger>
            </TabsList>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 bg-background">
            <TabsContent value="hooks" className="mt-0 h-full">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Laboratório de Ganchos (Hooks)</h3>
                  <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">IA Gerou 5 Variações</Badge>
                </div>
                <div className="grid gap-3">
                  {[
                    { id: 1, text: "90% das pessoas desistem exatamente quando estão prestes a vencer. Não seja uma delas.", score: 95 },
                    { id: 2, text: "O segredo obscuro sobre a motivação que os bilionários não querem que você saiba.", score: 88 },
                    { id: 3, text: "Pare de rolar a tela se você quer mudar de vida nos próximos 30 dias.", score: 82 },
                  ].map((hook) => (
                    <Card key={hook.id} className="cursor-pointer hover:border-primary transition-all duration-200">
                      <CardContent className="p-4 flex items-center justify-between">
                        <p className="text-foreground font-medium">{hook.text}</p>
                        <Badge variant={hook.score > 90 ? "default" : "secondary"}>Score: {hook.score}</Badge>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="titles" className="mt-0 h-full">
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Módulo de Títulos em Desenvolvimento...
              </div>
            </TabsContent>
            
            {/* Outras abas omitidas para brevidade, mas o layout suporta todas */}
          </div>
        </Tabs>
      </Card>
    </div>
  );
}
