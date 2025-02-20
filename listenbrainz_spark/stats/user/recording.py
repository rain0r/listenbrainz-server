from listenbrainz_spark.stats import run_query


def get_recordings(table: str, number_of_results: int):
    """
    Get recording information (recording_name, recording_mbid etc) for every user
    ordered by listen count (number of times a user has listened to the track/recording).

    Args:
        table: name of the temporary table
        number_of_results: number of top results to keep per user.

    Returns:
        iterator (iter): an iterator over result:
                {
                    'user1' : [
                        {
                            'track_name': str,
                            'recording_mbid': str,
                            'artist_name': str,
                            'artist_credit_id': int,
                            'release_name': str,
                            'release_mbid': str,
                            'listen_count': int
                        }
                    ],
                    'user2' : [{...}],
                }
    """
    result = run_query(f"""
        WITH intermediate_table as (
            SELECT user_id
                 , first(recording_name) AS any_recording_name
                 , recording_mbid
                 , first(artist_name) AS any_artist_name
                 , artist_credit_mbids
                 , nullif(first(release_name), '') as any_release_name
                 , release_mbid
                 , count(*) as listen_count
              FROM {table}
          GROUP BY user_id
                 , lower(recording_name)
                 , recording_mbid
                 , lower(artist_name)
                 , artist_credit_mbids
                 , lower(release_name)
                 , release_mbid
        ), ranked_stats as (
            SELECT user_id
                 , any_recording_name AS track_name
                 , recording_mbid
                 , any_release_name AS release_name
                 , release_mbid
                 , any_artist_name AS artist_name
                 , artist_credit_mbids
                 , listen_count
                 , row_number() OVER (PARTITION BY user_id ORDER BY listen_count DESC) AS rank
              FROM intermediate_table
        )
        SELECT user_id
             , sort_array(
                    collect_list(
                        struct(
                            listen_count
                          , track_name
                          , recording_mbid
                          , artist_name
                          , coalesce(artist_credit_mbids, array()) AS artist_mbids
                          , release_name
                          , release_mbid
                        )
                    )
                   , false
                ) as recordings
          FROM ranked_stats
         WHERE rank < {number_of_results}
      GROUP BY user_id
        """)

    return result.toLocalIterator()
