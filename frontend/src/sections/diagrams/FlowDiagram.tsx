import { useId } from 'react'

interface FlowDiagramProps {
  title: string
  desc: string
  /** Each layer is a row of boxes; a layer with two boxes shows a link between them. */
  layers: string[][]
}

const WIDTH = 360
const BOX_X = 22
const BOX_W = 316
const GAP_X = 24
const LINE_H = 17
const PAD_Y = 10
const GAP_Y = 26

function wrap(text: string, maxChars: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(' ')) {
    const candidate = line ? `${line} ${word}` : word
    if (candidate.length > maxChars && line) {
      lines.push(line)
      line = word
    } else {
      line = candidate
    }
  }
  if (line) lines.push(line)
  return lines
}

/**
 * Own architecture diagram drawn as accessible SVG (IMG-02). The text is real <text>, so it
 * is translated, selectable and readable by screen readers through <title> and <desc>.
 */
export function FlowDiagram({ title, desc, layers }: FlowDiagramProps) {
  const uid = useId()
  const titleId = `${uid}-title`
  const descId = `${uid}-desc`
  const markerId = `${uid}-arrow`

  const layout = layers.reduce<{
    rows: Array<{ y: number; height: number; boxW: number; wrapped: string[][] }>
    next: number
  }>(
    (acc, boxes) => {
      const boxW = boxes.length === 1 ? BOX_W : (BOX_W - GAP_X) / 2
      const wrapped = boxes.map((label) => wrap(label, boxes.length === 1 ? 38 : 17))
      const height = Math.max(...wrapped.map((lines) => lines.length)) * LINE_H + PAD_Y * 2
      return {
        rows: [...acc.rows, { y: acc.next, height, boxW, wrapped }],
        next: acc.next + height + GAP_Y,
      }
    },
    { rows: [], next: 6 },
  )
  const { rows } = layout
  const totalHeight = layout.next - GAP_Y + 6

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${totalHeight}`}
      role="img"
      aria-labelledby={`${titleId} ${descId}`}
      className="h-auto w-full max-w-sm text-ink"
    >
      <title id={titleId}>{title}</title>
      <desc id={descId}>{desc}</desc>
      <defs>
        <marker
          id={markerId}
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto"
        >
          <path d="M1 1 9 5 1 9" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </marker>
      </defs>

      {rows.map((row, rowIndex) => (
        <g key={rowIndex}>
          {row.wrapped.map((lines, boxIndex) => {
            const x = row.wrapped.length === 1 ? BOX_X : BOX_X + boxIndex * (row.boxW + GAP_X)
            return (
              <g key={boxIndex}>
                <rect
                  x={x}
                  y={row.y}
                  width={row.boxW}
                  height={row.height}
                  rx="6"
                  className="fill-surface stroke-line-strong"
                  strokeWidth="1.2"
                />
                <text
                  x={x + row.boxW / 2}
                  y={row.y + PAD_Y + 12}
                  textAnchor="middle"
                  fontSize="13"
                  className="fill-current"
                >
                  {lines.map((line, lineIndex) => (
                    <tspan key={lineIndex} x={x + row.boxW / 2} dy={lineIndex === 0 ? 0 : LINE_H}>
                      {line}
                    </tspan>
                  ))}
                </text>
              </g>
            )
          })}
          {row.wrapped.length === 2 && (
            <line
              x1={BOX_X + row.boxW + 2}
              x2={BOX_X + row.boxW + GAP_X - 2}
              y1={row.y + row.height / 2}
              y2={row.y + row.height / 2}
              stroke="currentColor"
              strokeWidth="1.4"
              markerEnd={`url(#${markerId})`}
            />
          )}
          {rowIndex < rows.length - 1 && (
            <line
              x1={WIDTH / 2}
              x2={WIDTH / 2}
              y1={row.y + row.height + 2}
              y2={row.y + row.height + GAP_Y - 2}
              stroke="currentColor"
              strokeWidth="1.4"
              markerEnd={`url(#${markerId})`}
            />
          )}
        </g>
      ))}
    </svg>
  )
}
