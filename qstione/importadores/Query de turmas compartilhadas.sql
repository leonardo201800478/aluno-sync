WITH duplicadas AS (
    SELECT turma, disciplina
    FROM lyceum.dbo.LY_MATRICULA
    WHERE ano = '2026' AND semestre = 2
    GROUP BY turma, disciplina
    HAVING COUNT(*) > 1   -- combinações de turma+disciplina com mais de uma ocorrência
)
SELECT DISTINCT
    m.turma,
    m.disciplina,
    m.disciplina + '-COM' AS disciplina_com,   -- nova coluna
    a.CURSO
FROM 
    lyceum.dbo.LY_MATRICULA m
    INNER JOIN lyceum.dbo.LY_ALUNO a ON m.aluno = a.ALUNO
WHERE 
    m.ano = '2026' 
    AND m.semestre = 2
    AND EXISTS (
        SELECT 1 
        FROM duplicadas d 
        WHERE d.turma = m.turma AND d.disciplina = m.disciplina
    )
ORDER BY 
    disciplina_com;