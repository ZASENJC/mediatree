import { Movie } from '../api'

interface Props {
  movie: Movie
}

export default function JavdbPanel({ movie }: Props) {
  const comments = movie.javdb_comments || []

  return (
    <div className="p-4 bg-dark-800 rounded-lg">
      <h3 className="text-sm font-semibold mb-3 text-gray-300 flex items-center gap-2">
        <span className="text-blue-400">[i]</span> JAVDB 信息
      </h3>

      <div className="space-y-2 text-sm">
        {movie.javdb_score != null && movie.javdb_score > 0 && (
          <div className="flex justify-between">
            <span className="text-gray-500">评分</span>
            <span className="text-yellow-400 font-semibold">{movie.javdb_score.toFixed(1)} / 5.0</span>
          </div>
        )}
        {movie.javdb_likes != null && movie.javdb_likes > 0 && (
          <div className="flex justify-between">
            <span className="text-gray-500">喜欢数</span>
            <span className="text-pink-400">like {movie.javdb_likes.toLocaleString()}</span>
          </div>
        )}
        {comments.length > 0 && (
          <div className="mt-3 pt-3 border-t border-dark-700">
            <p className="text-xs text-gray-500 mb-2">评论 ({comments.length})</p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {comments.map((comment, i) => (
                <p key={i} className="text-xs text-gray-400 leading-relaxed bg-dark-700/50 p-2 rounded">
                  {comment}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
