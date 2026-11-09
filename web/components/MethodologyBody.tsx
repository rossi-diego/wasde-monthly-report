"use client";

// The methodology in both languages. Long-form copy is written per language (not key by key),
// and every number in it comes from the build (meta.json, insights.json gates).

import { useLang } from "@/components/chrome/I18n";
import { monthYear, num } from "@/lib/format";

export type MethodFacts = {
  reports: number;
  rows: number;
  first: string; // "2010-07"
  last: string; // "2026-10"
  minN: number;
  pctlN: number;
  smallN: number;
  f2Months: number;
  nScreened: Record<string, number> | null;
  homeHidden: number[]; // months the Crop Progress card is off the home page
};

function Block({ title, id, children }: { title: string; id?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="card max-w-3xl scroll-mt-4 space-y-3 p-5 sm:p-6">
      <h2 className="m-0 text-[17px] font-bold">{title}</h2>
      <div className="space-y-3 leading-relaxed">{children}</div>
    </section>
  );
}

const S = ({ children }: { children: React.ReactNode }) => <strong className="text-ink">{children}</strong>;

function En({ f }: { f: MethodFacts }) {
  const screened = f.nScreened ? Object.entries(f.nScreened).map(([k, v]) => `${k} ${num(v)}`).join(", ") : null;
  return (
    <>
      <p className="m-0 max-w-3xl text-muted">
        How the numbers on this site are collected, harmonized and turned into insight. Everything is open source and rebuilt from the raw USDA files on
        every run.
      </p>

      <Block title="Sources">
        <p>
          <S>WASDE, 2021 onwards:</S> USDA&apos;s official machine-readable CSV, one file per report. <S>July 2010 – 2020</S> (and any month without a
          CSV): the XML edition archived by ESMIS (Cornell / USDA National Agricultural Library), discovered through its public API. Earlier reports exist
          only as PDF/text and are out of scope.
        </p>
        <p>
          The WASDE dataset currently holds {num(f.reports)} reports ({monthYear(f.first, "en")} – {monthYear(f.last, "en")}) and {num(f.rows)} values.
          Months without a WASDE (the October 2013 and October 2025 government shutdowns) are simply absent. The other four reports (Export Sales, NASS
          crush, Crop Progress, Grain Stocks) are described below; every source is US Government work in the public domain.
        </p>
      </Block>

      <Block title="Harmonization">
        <p>
          The XML edition does not label commodities or units for most tables. Its layout was learned from the 53 months (2021–2025) published in both
          formats: 97% of CSV values are reproduced exactly from the XML, and 100% of the grain and oilseed balance sheets. Label variants (e.g. &quot;Hard
          Winter&quot; vs &quot;Hard Red Winter&quot;) are aliased in versioned configuration files.
        </p>
        <p>
          Every table, commodity, line and unit gets a canonical id (e.g. &quot;Ending Stocks, Total&quot; and &quot;Ending stocks&quot; →{" "}
          <code>ending_stocks</code>). A label never seen before stops the run until it is mapped, so nothing is silently dropped.
        </p>
        <p>
          Continuity choices: &quot;EU-27&quot; (2010–2013), &quot;European Union&quot; and &quot;EU-27+UK&quot; (Jan–Apr 2021) form one European Union
          series. Older reports publish projected farm prices as ranges (e.g. 7.50–8.90); these are stored as the midpoint. Units follow the official CSV,
          and labels that are wrong at the source (cotton farm price tagged as bales) are corrected.
        </p>
        <p>
          Known gaps in the pre-2021 history: WASDE&apos;s projection-reliability tables, some quarterly livestock lines, and the U.S. milk table, whose
          fat- and skim-solids blocks share labels in the XML. Footnoted &quot;negligible&quot; cells in old cotton tables are stored as missing, not zero.
        </p>
      </Block>

      <Block title="Definitions">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <S>Stocks-to-use</S>: ending stocks ÷ use. For World and World ex-China, use = domestic use. For the U.S. and individual countries, use =
            domestic use + exports. Where a table publishes no domestic total (U.S. soybeans), it is total use − exports.
          </li>
          <li>
            <S>Revision path</S>: the value USDA published for one marketing year in each successive report. Month 0 is the first projection in May; month
            12 is when the projection becomes an estimate.
          </li>
          <li>
            <S>Drivers</S>: Δ ending stocks = Δ beginning stocks + Δ production + Δ imports − Δ domestic use − Δ exports + other. For U.S. tables
            production splits into an area effect (Δ area × previous yield) and a yield effect (the rest).
          </li>
          <li>
            <S>Percentile</S>: shown only once at least {f.pctlN} comparable values exist; otherwise ranks read &quot;k of n&quot;.
          </li>
        </ul>
      </Block>

      <Block title="How WASDE headlines are chosen">
        <ol className="list-decimal space-y-2 pl-5">
          <li>Candidates: ending stocks, production, yield, area, exports, crush and farm price of the focus commodities, for the new- and old-crop years.</li>
          <li>Each change must clear an absolute materiality floor (e.g. 50 mil. bu for U.S. corn ending stocks, 2 MMT for world stocks).</li>
          <li>Score = half &quot;size&quot; (percent change) and half &quot;surprise&quot; (change ÷ the median change of the same line in the same month of past years).</li>
          <li>One headline per commodity, region and marketing year, at most two per commodity, six in total.</li>
        </ol>
      </Block>

      <Block title="Export Sales (USDA FAS)" id="export-sales">
        <p>
          Weekly Export Sales Reporting (ESR) data from the FAS API, published Thursdays at 8:30 ET for the week ending the previous Thursday. Metric
          tonnes for the current marketing year; next-marketing-year sales are kept separate. Commitments = accumulated exports + outstanding sales. ESR
          commitments are not Census exports.
        </p>
        <p>
          <S>Pace vs USDA (E1)</S>: commitments ÷ the U.S. export projection of the latest WASDE released before that ESR (an as-of join on release
          timestamps, so no look-ahead), converted to metric tonnes. Each of the 5 previous marketing years is measured the same way, at the same week,
          against the WASDE public at the time. Five years is a small sample: shown as a mean and a min–max range, never as a percentile.{" "}
          <S>Required weekly sales (E2)</S>: (as-of target − commitments) ÷ weeks left, vs the 4-week average of net sales; not shown with fewer than 6
          weeks left. <S>China share (E3)</S>: always next to the share of unknown destinations, which can hide China.
        </p>
        <p>
          Vintages: the API serves only the latest revision of past weeks, so history before the first capture is latest-only; every pull is stored as an
          immutable snapshot from then on. Shutdown catch-up weeks (2013, 2018–19, 2025) are pinned to their actual FAS release dates.
        </p>
      </Block>

      <Block title="Soybean crush (USDA NASS Fats & Oils)" id="crush">
        <p>
          The monthly NASS report <em>Fats and Oils: Oilseed Crushings, Production, Consumption and Stocks</em>, released about the first business day of
          each month at 15:00 ET for the month two months earlier. Each release zip is found through the ESMIS API and stored byte-for-byte; every printed
          value is kept with the release that printed it. Tons are short tons (2,000 lb), oil is in 1,000 lb, bushels = short tons × 33.3333.{" "}
          <S>History window: 2015-10+</S> (ESMIS holds NASS files from the October 2015 release only).
        </p>
        <p>
          <S>Crush pace (F1)</S>: marketing-year-to-date crush ÷ the WASDE crush projection public when NASS first printed that month; the 5 previous years
          measured the same way. <S>Still needed (F2)</S>: (projection − crush to date) ÷ months left, vs the same months last year; not shown with fewer
          than {f.f2Months} months left. <S>Oil yield (F3)</S>: crude oil × 1,000 ÷ bushels crushed, vs the same month of 5 years and the WASDE-implied
          yield.
        </p>
        <p>
          NOPA members represent roughly 95% of US soybean crush and publish about two weeks earlier; NOPA data is proprietary and not redistributed here.
          See <a href="https://www.nopa.org/" className="text-link underline">nopa.org</a>.
        </p>
      </Block>

      <Block title="Crop Progress (USDA NASS)" id="crop-progress">
        <p>
          The weekly NASS <em>Crop Progress</em> report, released Mondays at 16:00 ET from April to November (Tuesday after a federal holiday), covering
          the week ending the previous Sunday. Release zips are found through the ESMIS API and stored as published; the national figure is NASS&apos;s
          own &quot;selected states&quot; aggregate (e.g. 18 states for corn). Kept: corn, soybeans, winter wheat and spring wheat; the stage tables
          (cumulative % of acreage planted, emerged, … harvested) with NASS&apos;s previous week, previous year and 5-year average, and the condition
          table (very poor … excellent). History starts with the first file the pipeline reads in full (June 2010).
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <S>Good/excellent (C1)</S>: GE = good% + excellent%, against NASS&apos;s published previous-year value and against the 5 previous seasons.
            NASS publishes no 5-year average for condition, so that one is computed here: for each prior season, the week whose day of the year is
            nearest (within ±3 days). n is the number of seasons found; fewer than {f.minN} suppresses the finding.
          </li>
          <li>
            <S>Stage pace (C2)</S>: % of acreage at the stage in progress minus NASS&apos;s own published 5-year average (used exactly as published; no
            recomputation).
          </li>
          <li>
            <S>Condition index (C3)</S>: CI = (1·very poor + 2·poor + 3·fair + 4·good + 5·excellent) ÷ 100, from 1 to 5; vs the 5 prior seasons at the same
            week (same ±3-day rule).
          </li>
          <li>
            <S>Season closed</S>: after the last scheduled release of the season, the card reads &quot;Season closed: final GE X% vs 5-yr Y%&quot; (the
            final rating of each crop against the final ratings of the 5 prior seasons); C2 and C3 are not shown, the report is marked off-season rather
            than stale, and the card leaves the home page in months {f.homeHidden.join(", ")} (December to March).
          </li>
        </ul>
      </Block>

      <Block title="Grain Stocks (USDA NASS)" id="grain-stocks">
        <p>
          The quarterly NASS <em>Grain Stocks</em> report (12:00 ET): stocks of corn, soybeans and wheat on December 1, March 1, June 1 and September 1,
          on and off farms. History from the June 2010 release; each release is stored as published, and a quarter revised by the next release keeps its
          first print.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <S>Stocks vs WASDE (G1)</S>: only for the stock date that matches a WASDE ending-stocks estimate (corn and soybeans September 1, wheat June 1).
            Gap = NASS total (first print) − the old-crop ending stocks of the WASDE public at the Grain Stocks release (as-of join, no look-ahead), in
            million bushels and %, ranked by the size of the gap among every year since 2010 (n ≈ 16).
          </li>
          <li>
            <S>Implied use (G2)</S>: stocks at the start of the quarter + production − stocks at the end. Production is the WASDE figure public at the
            release, in the harvest quarter only (corn and soybeans September → December 1, wheat June → September 1), otherwise 0. Compared with the same
            quarter of the 5 previous years. Caveats: imports omitted; small for corn/soy. NASS may revise production on the same day (Small Grains Summary
            / annual Crop Production); this uses the WASDE figure public at release.
          </li>
          <li>
            <S>On-farm share (G3)</S>: on-farm stocks ÷ total, vs the same date of the 5 previous years, and total stocks vs a year earlier.
          </li>
        </ul>
      </Block>

      <Block title="Commodity pages" id="lenses">
        <p>
          /commodities/soybeans and /commodities/corn put the latest number of every report that covers the commodity on one page (WASDE balance sheet,
          Export Sales commitments, crush, Crop Progress, Grain Stocks), each with its release date, a link to the report chapter it comes from and the
          files in the catalogue. Nothing is recomputed there: the numbers are the report pages&apos; own.
        </p>
      </Block>

      <Block title="Insight rules and honesty gates" id="rules">
        <ul className="list-disc space-y-2 pl-5">
          <li>Insights are computed in Python as typed parameters (ranks, shares, n); the site only turns them into words in English or Portuguese, and a test checks that the page matches the JSON.</li>
          <li>
            Ranks read &quot;k of n&quot;. A percentile appears only when n ≥ {f.pctlN}. n is always shown, with a &quot;small sample&quot; chip below {f.smallN}.
          </li>
          <li>An insight is not shown when n &lt; {f.minN}, when an input report is older than its cadence plus grace (checked against the release that uses it), or when no USDA projection was public at the time.</li>
          <li>
            The home row holds at most 5 cards: one per report plus one cross-report card; a report left out by that cap appears under &quot;Also released&quot;
            with the same rules.
          </li>
          {screened && <li>Multiple comparisons: this build screened {screened} series or candidates.</li>}
        </ul>
      </Block>

      <Block title="Automation" id="automation">
        <p>
          A scheduled GitHub Actions workflow runs every 30 minutes on weekdays. A light gate checks the release calendars first and stops in seconds when
          nothing is due. When a new report appears it rebuilds bronze → silver → gold (dbt + DuckDB, with data tests such as the balance-sheet identity,
          monotonic crop progress, condition shares summing to 100 and a no-look-ahead check), redeploys this site, verifies it live and only then
          publishes the versioned GitHub release. Crop Progress is caught on Monday evening runs; a late NASS posting is picked up by Tuesday&apos;s first
          run.
        </p>
        <p>
          A new WASDE becomes the <code>data-YYYY-MM</code> release, always marked Latest. Any other build with new data publishes an immutable{" "}
          <code>weekly-YYYY-MM-DD</code> prerelease, never marked Latest. Each report is isolated: a failed pull keeps the last good data, is flagged on the
          Reports page and never blocks the others. Superseded weekly prereleases are pruned after a documented window; <code>data-*</code> releases are
          kept forever.
        </p>
      </Block>
    </>
  );
}

function Pt({ f }: { f: MethodFacts }) {
  const screened = f.nScreened ? Object.entries(f.nScreened).map(([k, v]) => `${k} ${num(v)}`).join(", ") : null;
  return (
    <>
      <p className="m-0 max-w-3xl text-muted">
        Como os números deste site são coletados, harmonizados e transformados em insight. Tudo é código aberto e reconstruído a partir dos arquivos
        originais do USDA a cada execução.
      </p>

      <Block title="Fontes">
        <p>
          <S>WASDE, de 2021 em diante:</S> o CSV oficial legível por máquina do USDA, um arquivo por relatório. <S>Julho de 2010 – 2020</S> (e qualquer mês
          sem CSV): a edição XML arquivada pelo ESMIS (Cornell / Biblioteca Nacional de Agricultura do USDA), encontrada pela sua API pública. Relatórios
          anteriores existem só em PDF/texto e ficam fora do escopo.
        </p>
        <p>
          O dataset do WASDE tem hoje {num(f.reports)} relatórios ({monthYear(f.first, "pt")} – {monthYear(f.last, "pt")}) e {num(f.rows)} valores. Meses
          sem WASDE (as paralisações do governo de outubro de 2013 e outubro de 2025) simplesmente não aparecem. Os outros quatro relatórios (Export Sales,
          esmagamento do NASS, Crop Progress, Grain Stocks) estão descritos abaixo; todas as fontes são obras do governo dos EUA, em domínio público.
        </p>
      </Block>

      <Block title="Harmonização">
        <p>
          A edição XML não rotula commodities nem unidades na maioria das tabelas. Seu layout foi aprendido com os 53 meses (2021–2025) publicados nos dois
          formatos: 97% dos valores do CSV são reproduzidos exatamente a partir do XML, e 100% dos balanços de grãos e oleaginosas. Variantes de rótulo (ex.
          &quot;Hard Winter&quot; vs &quot;Hard Red Winter&quot;) são tratadas como apelidos em arquivos de configuração versionados.
        </p>
        <p>
          Cada tabela, commodity, linha e unidade recebe um id canônico (ex. &quot;Ending Stocks, Total&quot; e &quot;Ending stocks&quot; →{" "}
          <code>ending_stocks</code>). Um rótulo nunca visto antes interrompe a execução até ser mapeado, então nada é descartado em silêncio.
        </p>
        <p>
          Escolhas de continuidade: &quot;EU-27&quot; (2010–2013), &quot;European Union&quot; e &quot;EU-27+UK&quot; (jan–abr 2021) formam uma única série da
          União Europeia. Relatórios antigos publicam preços ao produtor projetados como faixas (ex. 7,50–8,90); guardamos o ponto médio. As unidades seguem
          o CSV oficial, e rótulos errados na origem (preço do algodão marcado como fardos) são corrigidos.
        </p>
        <p>
          Lacunas conhecidas no histórico anterior a 2021: as tabelas de confiabilidade das projeções do WASDE, algumas linhas trimestrais de pecuária e a
          tabela de leite dos EUA, cujos blocos de gordura e sólidos desnatados compartilham rótulos no XML. Células &quot;desprezíveis&quot; em notas de
          rodapé de tabelas antigas de algodão ficam como ausentes, não zero.
        </p>
      </Block>

      <Block title="Definições">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <S>Estoque/uso</S>: estoques finais ÷ uso. Para Mundo e Mundo ex-China, uso = uso doméstico. Para os EUA e países individuais, uso = uso
            doméstico + exportações. Onde a tabela não publica total doméstico (soja dos EUA), ele é o uso total − exportações.
          </li>
          <li>
            <S>Trajetória de revisão</S>: o valor que o USDA publicou para um ano-safra em cada relatório sucessivo. O mês 0 é a primeira projeção, em
            maio; no mês 12 a projeção vira estimativa.
          </li>
          <li>
            <S>Fatores</S>: Δ estoques finais = Δ estoques iniciais + Δ produção + Δ importações − Δ uso doméstico − Δ exportações + outros. Nas tabelas dos
            EUA a produção se divide em efeito área (Δ área × produtividade anterior) e efeito produtividade (o restante).
          </li>
          <li>
            <S>Percentil</S>: aparece só quando há pelo menos {f.pctlN} valores comparáveis; caso contrário, as posições são lidas como &quot;k de n&quot;.
          </li>
        </ul>
      </Block>

      <Block title="Como as manchetes do WASDE são escolhidas">
        <ol className="list-decimal space-y-2 pl-5">
          <li>Candidatos: estoques finais, produção, produtividade, área, exportações, esmagamento e preço ao produtor das commodities em foco, safra nova e velha.</li>
          <li>Cada mudança precisa passar de um piso absoluto de materialidade (ex. 50 mi bu para estoques finais de milho dos EUA, 2 mi t para estoques mundiais).</li>
          <li>Pontuação = metade &quot;tamanho&quot; (variação percentual) e metade &quot;surpresa&quot; (variação ÷ a mediana das variações da mesma linha no mesmo mês de anos anteriores).</li>
          <li>Uma manchete por commodity, região e ano-safra, no máximo duas por commodity, seis no total.</li>
        </ol>
      </Block>

      <Block title="Export Sales (USDA FAS)" id="export-sales">
        <p>
          Dados semanais do Export Sales Reporting (ESR) pela API do FAS, publicados às quintas, 8:30 ET, para a semana encerrada na quinta anterior.
          Toneladas métricas do ano-safra atual; vendas do próximo ano-safra ficam separadas. Compromissos = exportações acumuladas + vendas em aberto.
          Compromissos do ESR não são as exportações do Census.
        </p>
        <p>
          <S>Ritmo vs USDA (E1)</S>: compromissos ÷ a projeção de exportação dos EUA do último WASDE divulgado antes daquele ESR (junção pela data de
          divulgação, sem olhar o futuro), convertida em toneladas métricas. Cada um dos 5 anos-safra anteriores é medido do mesmo jeito, na mesma semana,
          contra o WASDE vigente na época. Cinco anos é amostra pequena: mostramos média e faixa mín–máx, nunca percentil.{" "}
          <S>Vendas semanais necessárias (E2)</S>: (meta vigente − compromissos) ÷ semanas restantes, vs a média de 4 semanas das vendas líquidas; não
          exibido com menos de 6 semanas restantes. <S>Participação da China (E3)</S>: sempre ao lado da parcela de destinos desconhecidos, que pode
          esconder a China.
        </p>
        <p>
          Versões: a API serve só a última revisão das semanas passadas, então o histórico antes da primeira captura é só a última revisão; daí em diante
          cada coleta é guardada como um retrato imutável. As semanas atrasadas pelas paralisações (2013, 2018–19, 2025) usam as datas reais de divulgação do
          FAS.
        </p>
      </Block>

      <Block title="Esmagamento de soja (USDA NASS Fats & Oils)" id="crush">
        <p>
          O relatório mensal do NASS <em>Fats and Oils: Oilseed Crushings, Production, Consumption and Stocks</em>, divulgado por volta do 1º dia útil de cada
          mês às 15:00 ET, com dados de dois meses antes. Cada zip é encontrado pela API do ESMIS e guardado byte a byte; todo valor impresso fica com a
          divulgação que o imprimiu. Tons são toneladas curtas (2.000 lb), óleo em 1.000 lb, bushels = toneladas curtas × 33,3333.{" "}
          <S>Janela histórica: 2015-10+</S> (o ESMIS tem arquivos do NASS só a partir da divulgação de outubro de 2015).
        </p>
        <p>
          <S>Ritmo de esmagamento (F1)</S>: esmagamento acumulado no ano-safra ÷ a projeção de esmagamento do WASDE vigente quando o NASS publicou o mês pela
          primeira vez; os 5 anos anteriores medidos do mesmo jeito. <S>Ainda necessário (F2)</S>: (projeção − esmagamento acumulado) ÷ meses restantes, vs
          os mesmos meses do ano anterior; não exibido com menos de {f.f2Months} meses restantes. <S>Rendimento de óleo (F3)</S>: óleo bruto × 1.000 ÷
          bushels esmagados, vs o mesmo mês de 5 anos e o rendimento implícito no WASDE.
        </p>
        <p>
          Os membros da NOPA respondem por cerca de 95% do esmagamento de soja dos EUA e publicam umas duas semanas antes; os dados da NOPA são proprietários
          e não são redistribuídos aqui. Veja <a href="https://www.nopa.org/" className="text-link underline">nopa.org</a>.
        </p>
      </Block>

      <Block title="Crop Progress (USDA NASS)" id="crop-progress">
        <p>
          O relatório semanal <em>Crop Progress</em> do NASS, divulgado às segundas, 16:00 ET, de abril a novembro (terça após feriado federal), para a
          semana encerrada no domingo anterior. Os zips são encontrados pela API do ESMIS e guardados como publicados; o número nacional é o agregado de
          &quot;estados selecionados&quot; do próprio NASS (ex. 18 estados para o milho). Mantidos: milho, soja, trigo de inverno e trigo de primavera; as
          tabelas de estágio (% acumulado da área plantada, emergida, … colhida) com a semana anterior, o ano anterior e a média de 5 anos do NASS, e a
          tabela de condição (muito ruim … excelente). O histórico começa no primeiro arquivo que o pipeline lê por completo (junho de 2010).
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <S>Boa/excelente (C1)</S>: BE = boa% + excelente%, contra o valor do ano anterior publicado pelo NASS e contra as 5 safras anteriores. O NASS não
            publica média de 5 anos para condição, então ela é calculada aqui: em cada safra anterior, a semana com o dia do ano mais próximo (até ±3
            dias). n é o número de safras encontradas; menos de {f.minN} suprime o destaque.
          </li>
          <li>
            <S>Ritmo do estágio (C2)</S>: % da área no estágio em andamento menos a média de 5 anos publicada pelo próprio NASS (usada exatamente como
            publicada, sem recálculo).
          </li>
          <li>
            <S>Índice de condição (C3)</S>: IC = (1·muito ruim + 2·ruim + 3·regular + 4·boa + 5·excelente) ÷ 100, de 1 a 5; vs as 5 safras anteriores na
            mesma semana (mesma regra de ±3 dias).
          </li>
          <li>
            <S>Safra encerrada</S>: depois da última divulgação prevista da safra, o cartão diz &quot;Safra encerrada: BE final X% vs 5 anos Y%&quot; (a
            avaliação final de cada lavoura contra as avaliações finais das 5 safras anteriores); C2 e C3 não aparecem, o relatório fica marcado como
            entressafra e não como desatualizado, e o cartão sai da página inicial nos meses {f.homeHidden.join(", ")} (dezembro a março).
          </li>
        </ul>
      </Block>

      <Block title="Grain Stocks (USDA NASS)" id="grain-stocks">
        <p>
          O relatório trimestral <em>Grain Stocks</em> do NASS (12:00 ET): estoques de milho, soja e trigo em 1º de dezembro, 1º de março, 1º de junho e 1º de
          setembro, nas fazendas e fora delas. Histórico desde a divulgação de junho de 2010; cada divulgação é guardada como publicada, e um trimestre
          revisado pela divulgação seguinte mantém a primeira publicação.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <S>Estoques vs WASDE (G1)</S>: só para a data que corresponde a uma estimativa de estoques finais do WASDE (milho e soja 1º de setembro, trigo 1º
            de junho). Diferença = total do NASS (primeira publicação) − os estoques finais da safra velha no WASDE público na divulgação do Grain Stocks
            (sem olhar o futuro), em milhões de bushels e %, ordenada pelo tamanho entre todos os anos desde 2010 (n ≈ 16).
          </li>
          <li>
            <S>Uso implícito (G2)</S>: estoques no início do trimestre + produção − estoques no fim. A produção é o número do WASDE público na divulgação,
            só no trimestre da colheita (milho e soja setembro → 1º de dezembro, trigo junho → 1º de setembro); nos outros, 0. Comparado com o mesmo trimestre
            dos 5 anos anteriores. Ressalvas: importações omitidas; pequenas para milho/soja. O NASS pode revisar a produção no mesmo dia (Small Grains
            Summary / Crop Production anual); aqui se usa o número do WASDE público na divulgação.
          </li>
          <li>
            <S>Parcela nas fazendas (G3)</S>: estoques nas fazendas ÷ total, vs a mesma data dos 5 anos anteriores, e estoques totais vs um ano antes.
          </li>
        </ul>
      </Block>

      <Block title="Páginas por commodity" id="lenses">
        <p>
          /commodities/soybeans e /commodities/corn reúnem numa página o número mais recente de cada relatório que cobre a commodity (balanço do WASDE,
          compromissos do Export Sales, esmagamento, Crop Progress, Grain Stocks), cada um com a data de divulgação, um link para o capítulo de onde vem e os
          arquivos do catálogo. Nada é recalculado ali: os números são os das páginas de cada relatório.
        </p>
      </Block>

      <Block title="Regras de insight e critérios de honestidade" id="rules">
        <ul className="list-disc space-y-2 pl-5">
          <li>Os insights são calculados em Python como parâmetros tipados (posições, parcelas, n); o site só os transforma em palavras, em inglês ou português, e um teste confere que a página bate com o JSON.</li>
          <li>
            Posições são lidas como &quot;k de n&quot;. Percentil só aparece com n ≥ {f.pctlN}. n é sempre mostrado, com o selo &quot;amostra pequena&quot;
            abaixo de {f.smallN}.
          </li>
          <li>Um insight não aparece quando n &lt; {f.minN}, quando um relatório de entrada é mais velho que sua cadência mais a tolerância (conferido contra a divulgação que o usa) ou quando nenhuma projeção do USDA era pública na época.</li>
          <li>
            A linha da página inicial tem no máximo 5 cartões: um por relatório e um entre relatórios; um relatório que fica de fora por esse limite aparece
            em &quot;Também divulgados&quot;, com as mesmas regras.
          </li>
          {screened && <li>Comparações múltiplas: esta versão avaliou {screened} séries ou candidatos.</li>}
        </ul>
      </Block>

      <Block title="Automação" id="automation">
        <p>
          Um workflow agendado do GitHub Actions roda a cada 30 minutos nos dias úteis. Um filtro leve confere primeiro os calendários de divulgação e para
          em segundos quando nada está previsto. Quando aparece um relatório novo, ele reconstrói bronze → silver → gold (dbt + DuckDB, com testes de dados
          como a identidade do balanço, progresso das lavouras monotônico, condições somando 100 e uma checagem contra olhar o futuro), publica o site de
          novo, confere o site no ar e só então publica a release versionada no GitHub. O Crop Progress é capturado nas execuções de segunda à noite; uma
          publicação atrasada do NASS entra na primeira execução de terça.
        </p>
        <p>
          Um WASDE novo vira a release <code>data-YYYY-MM</code>, sempre marcada como Latest. Qualquer outra versão com dados novos publica uma prerelease
          imutável <code>weekly-YYYY-MM-DD</code>, nunca marcada como Latest. Cada relatório é isolado: uma coleta com falha mantém os últimos dados bons, é
          sinalizada na página Relatórios e nunca bloqueia os outros. Prereleases semanais superadas são removidas depois de uma janela documentada;
          releases <code>data-*</code> ficam para sempre.
        </p>
      </Block>
    </>
  );
}

export default function MethodologyBody({ f }: { f: MethodFacts }) {
  const { lang } = useLang();
  return <div className="flex flex-col gap-5">{lang === "pt" ? <Pt f={f} /> : <En f={f} />}</div>;
}
