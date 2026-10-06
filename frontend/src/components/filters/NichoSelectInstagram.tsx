import { useNichosInstagram } from "@/hooks/useNichosInstagram"
import { SelectComVazio } from "@/components/filters/SelectComVazio"

interface NichoSelectInstagramProps {
  valor: string
  onChange: (valor: string) => void
}

export function NichoSelectInstagram({
  valor,
  onChange,
}: NichoSelectInstagramProps) {
  const { data: nichos } = useNichosInstagram()

  return (
    <SelectComVazio
      valor={valor}
      onChange={onChange}
      opcoes={(nichos ?? []).map((nicho) => ({ valor: nicho, label: nicho }))}
      labelVazio="Todos os nichos"
      placeholder="Nicho"
      className="w-[200px]"
    />
  )
}
