import { useFunilCombinado } from "@/hooks/useCombinado"
import { FunilConversaoChart } from "@/components/dashboard/FunilConversaoChart"

export function FunilConversaoCombinado() {
  const { data, isLoading } = useFunilCombinado()

  return <FunilConversaoChart estagios={data?.estagios} isLoading={isLoading} />
}
